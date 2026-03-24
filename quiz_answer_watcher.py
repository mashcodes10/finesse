#!/usr/bin/env python3
"""
Quiz Answer Watcher — Claude Vision
Polls Oracle Cloud for screenshots containing quiz/MCQ questions,
processes them in batches of 3 with Claude API,
returns ONLY answers (no explanations),
and uploads the response back to Oracle Cloud so the Mac overlay can display it.

Monitors: quiz-screenshots/ folder in screenshot-bucket
Response written to: responses/latest_response.txt

NOTE: Set Mac daemon's upload_folder = "quiz-screenshots/" to use this watcher.
"""

import os
import sys
import time
import json
import base64
import logging
import io
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import oci
from oci.auth.signers import InstancePrincipalsSecurityTokenSigner
import anthropic
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/quiz_answer_watcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class QuizAnswerWatcher:
    def __init__(self):
        try:
            signer = InstancePrincipalsSecurityTokenSigner()
            self.object_storage = oci.object_storage.ObjectStorageClient(config={}, signer=signer)
            self.namespace = self.object_storage.get_namespace().data
            logger.info(f"Oracle Cloud initialized — namespace: {self.namespace}")
        except Exception as e:
            logger.error(f"Failed to initialize Oracle Cloud: {e}")
            sys.exit(1)

        self.bucket_name = "screenshot-bucket"
        self.screenshot_folder = "quiz-screenshots/"
        self.response_object = "responses/latest_response.txt"

        self.batch_size = 3
        self.pending_screenshots = []
        self.processed_files = set()
        self.state_file = Path("/tmp/quiz_processed_screenshots.json")
        self._load_state()

        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            logger.error("ANTHROPIC_API_KEY environment variable not set")
            sys.exit(1)
        self.claude = anthropic.Anthropic(api_key=api_key)

        logger.info(f"Quiz Answer Watcher ready — batch size: {self.batch_size}")
        logger.info(f"Watching: {self.bucket_name}/{self.screenshot_folder}")

    # ── State management ──────────────────────────────────────────────────────

    def _load_state(self):
        try:
            if self.state_file.exists():
                data = json.loads(self.state_file.read_text())
                self.processed_files = set(data.get('processed_files', []))
                logger.info(f"Loaded {len(self.processed_files)} processed files from state")
        except Exception as e:
            logger.warning(f"Could not load state: {e}")
            self.processed_files = set()

    def _save_state(self):
        try:
            data = {
                'processed_files': list(self.processed_files),
                'last_updated': datetime.now().isoformat()
            }
            self.state_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Could not save state: {e}")

    # ── Cloud operations ──────────────────────────────────────────────────────

    def get_new_screenshots(self) -> List[str]:
        try:
            resp = self.object_storage.list_objects(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                prefix=self.screenshot_folder,
                fields="name,timeCreated"
            )
            new = [
                obj.name for obj in resp.data.objects
                if obj.name not in self.processed_files
                and obj.name.lower().endswith('.png')
            ]
            if new:
                logger.info(f"Found {len(new)} new screenshot(s)")
            return new
        except Exception as e:
            logger.error(f"Error listing objects: {e}")
            return []

    def download_screenshot(self, name: str) -> Optional[bytes]:
        try:
            resp = self.object_storage.get_object(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                object_name=name
            )
            data = resp.data.content
            logger.info(f"Downloaded {Path(name).name} ({len(data):,} bytes)")
            return data
        except Exception as e:
            logger.error(f"Error downloading {name}: {e}")
            return None

    def upload_response(self, response: str):
        """Write the answer text back to Oracle Cloud for the Mac overlay to fetch."""
        try:
            self.object_storage.put_object(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                object_name=self.response_object,
                put_object_body=response.encode('utf-8'),
                content_type='text/plain'
            )
            logger.info(f"Response uploaded → {self.response_object}")
        except Exception as e:
            logger.error(f"Failed to upload response: {e}")

    def mark_existing_as_processed(self):
        """Skip screenshots already in the bucket when the watcher starts."""
        try:
            resp = self.object_storage.list_objects(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                prefix=self.screenshot_folder,
                fields="name"
            )
            count = 0
            for obj in resp.data.objects:
                if obj.name.lower().endswith('.png'):
                    self.processed_files.add(obj.name)
                    count += 1
            self._save_state()
            logger.info(f"Marked {count} existing screenshot(s) as already processed")
        except Exception as e:
            logger.error(f"Error marking existing screenshots: {e}")

    # ── Image compression ─────────────────────────────────────────────────────

    def compress_image(self, image_data: bytes, max_mb: float = 3.7) -> tuple:
        """Compress image to stay within Claude's 5 MB base64 limit."""
        try:
            size_mb = len(image_data) / (1024 * 1024)
            if size_mb <= max_mb:
                return image_data, "image/png"

            logger.info(f"Compressing image ({size_mb:.2f} MB)...")
            img = Image.open(io.BytesIO(image_data))
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')

            for quality in [85, 70, 55, 40]:
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=quality, optimize=True)
                compressed = buf.getvalue()
                if len(compressed) / (1024 * 1024) <= max_mb:
                    logger.info(f"Compressed to {len(compressed)/(1024*1024):.2f} MB (q={quality})")
                    return compressed, "image/jpeg"

            # Fallback: resize
            w, h = img.size
            for scale in [0.7, 0.5, 0.35]:
                resized = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                resized.save(buf, format='JPEG', quality=70, optimize=True)
                compressed = buf.getvalue()
                if len(compressed) / (1024 * 1024) <= max_mb:
                    logger.info(f"Resized+compressed to {len(compressed)/(1024*1024):.2f} MB (scale={scale})")
                    return compressed, "image/jpeg"

            return image_data, "image/png"
        except Exception as e:
            logger.error(f"Compression error: {e}")
            return image_data, "image/png"

    # ── Claude processing ─────────────────────────────────────────────────────

    def get_quiz_answers(self, images_data: List[bytes]) -> Optional[str]:
        """
        Send quiz screenshots to Claude.
        Returns ONLY the answers — no explanations.
        """
        try:
            content = [
                {
                    "type": "text",
                    "text": (
                        "The following screenshots contain quiz or multiple-choice questions. "
                        "Your task: look at every question and give ONLY the answer for each one. "
                        "No explanations. No reasoning. No extra text. "
                        "Number your answers to match the question numbers exactly.\n\n"
                        "Format:\n"
                        "1. <answer>\n"
                        "2. <answer>\n"
                        "3. <answer>\n"
                        "...and so on.\n\n"
                        "Now provide the answers for all questions in the screenshots:"
                    )
                }
            ]

            for i, image_data in enumerate(images_data):
                compressed, media_type = self.compress_image(image_data)
                b64 = base64.b64encode(compressed).decode('utf-8')
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64
                    }
                })
                logger.info(
                    f"Image {i+1}: {len(compressed)/(1024*1024):.2f} MB ({media_type}), "
                    f"base64: {len(b64.encode())/(1024*1024):.2f} MB"
                )

            logger.info(f"Sending {len(images_data)} screenshot(s) to Claude...")
            message = self.claude.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                messages=[{"role": "user", "content": content}]
            )

            if message.content:
                answers = message.content[0].text.strip()
                logger.info(
                    f"Received answers ({len(answers)} chars, "
                    f"{message.usage.input_tokens + message.usage.output_tokens} tokens)"
                )
                return answers

            logger.error("Empty response from Claude")
            return None

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None

    # ── Batch processing ──────────────────────────────────────────────────────

    def process_batch(self, names: List[str]):
        logger.info(f"Processing batch: {[Path(n).name for n in names]}")

        images = []
        for name in names:
            data = self.download_screenshot(name)
            if data:
                images.append(data)
            else:
                logger.warning(f"Skipping {name} (download failed)")

        if not images:
            logger.error("No images downloaded — skipping batch")
            for n in names:
                self.processed_files.add(n)
            self._save_state()
            return

        answers = self.get_quiz_answers(images)

        if answers:
            print("\n" + "=" * 60)
            print("QUIZ ANSWERS")
            print("=" * 60)
            print(answers)
            print("=" * 60 + "\n")
            self.upload_response(answers)
        else:
            logger.warning("No answers returned — check Claude response above")

        for n in names:
            self.processed_files.add(n)
        self._save_state()

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self, poll_interval: int = 15):
        logger.info("Skipping existing screenshots (only processing new ones)...")
        self.mark_existing_as_processed()
        logger.info(
            f"Watcher running — polling every {poll_interval}s, "
            f"waiting for {self.batch_size} screenshots per batch"
        )

        while True:
            try:
                new = self.get_new_screenshots()
                if new:
                    self.pending_screenshots.extend(new)
                    pending = len(self.pending_screenshots)
                    needed = self.batch_size - pending
                    logger.info(f"Queue: {pending}/{self.batch_size} — need {needed} more")

                    while len(self.pending_screenshots) >= self.batch_size:
                        batch = self.pending_screenshots[:self.batch_size]
                        self.pending_screenshots = self.pending_screenshots[self.batch_size:]
                        self.process_batch(batch)

                time.sleep(poll_interval)

            except KeyboardInterrupt:
                logger.info("Watcher stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(30)


if __name__ == "__main__":
    watcher = QuizAnswerWatcher()
    watcher.run(poll_interval=15)
