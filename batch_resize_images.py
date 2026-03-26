#!/usr/bin/env python3
"""
Batch resize PNG images in a multi-level directory structure.
Preserves the original directory hierarchy in the output.

Uses parallel processing by default for significant speedup on multi-core systems.
For text document scans, use --resampling nearest for upsampling
to preserve sharp edges and text clarity.

Vibe-coded with Claude Sonnet 4.5
Date: 2026-02-11
"""

import argparse
from pathlib import Path
from PIL import Image
from typing import Tuple, Optional
import sys
import signal
from tqdm import tqdm
from multiprocessing import Pool, cpu_count
from functools import partial
import signal


def resize_image(
    input_path: Path,
    output_path: Path,
    size: Tuple[int, int],
    maintain_aspect: bool = True,
    resampling: Image.Resampling = Image.Resampling.LANCZOS,
    quality: int = 95
) -> None:
    """
    Resize a single image and save to output path.
    
    Args:
        input_path: Path to input image
        output_path: Path to save resized image
        size: Target size as (width, height)
        maintain_aspect: If True, maintain aspect ratio (fit within size)
        resampling: Resampling filter (NEAREST, BILINEAR, BICUBIC, LANCZOS)
        quality: JPEG quality if converting format (1-100)
    """
    try:
        with Image.open(input_path) as img:
            if maintain_aspect:
                # Calculate aspect-preserving dimensions
                img_ratio = img.width / img.height
                target_ratio = size[0] / size[1]
                
                if img_ratio > target_ratio:
                    # Image is wider - fit to width
                    new_width = size[0]
                    new_height = int(size[0] / img_ratio)
                else:
                    # Image is taller - fit to height
                    new_height = size[1]
                    new_width = int(size[1] * img_ratio)
                
                img = img.resize((new_width, new_height), resampling)
            else:
                img = img.resize(size, resampling)
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save with original format
            img.save(output_path, optimize=True, quality=quality)
            
    except Exception as e:
        print(f"Error processing {input_path}: {e}", file=sys.stderr)


def _process_single_image(args):
    """Wrapper function for parallel processing."""
    input_path, output_path, size, maintain_aspect, resampling, quality = args
    resize_image(input_path, output_path, size, maintain_aspect, resampling, quality)


def _init_worker():
    """Initialize worker process to ignore SIGINT (Ctrl+C handled by main process only)."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def process_directory(
    input_dir: Path,
    output_dir: Path,
    size: Tuple[int, int],
    maintain_aspect: bool = True,
    resampling: Image.Resampling = Image.Resampling.LANCZOS,
    quality: int = 95,
    workers: int = 1,
    verbose: bool = False
) -> None:
    """
    Recursively process all PNG files in input directory.
    
    Args:
        input_dir: Root directory containing images
        output_dir: Root directory for output
        size: Target size as (width, height)
        maintain_aspect: If True, maintain aspect ratio
        resampling: Resampling filter to use
        quality: Image quality for saving
        workers: Number of parallel workers (1 = sequential)
        verbose: Print progress information
    """
    # Find all PNG files recursively (deduplicate for case-insensitive filesystems)
    png_files = sorted(set(list(input_dir.rglob("*.png")) + list(input_dir.rglob("*.PNG"))))
    
    if not png_files:
        print(f"No PNG files found in {input_dir}")
        return
    
    print(f"Found {len(png_files)} PNG files to process")
    
    # Prepare arguments for each image
    tasks = []
    for input_path in png_files:
        relative_path = input_path.relative_to(input_dir)
        output_path = output_dir / relative_path
        tasks.append((input_path, output_path, size, maintain_aspect, resampling, quality))
    
    # Process images
    try:
        if workers > 1:
            # Parallel processing with proper interrupt handling
            # Workers ignore SIGINT so only main process handles Ctrl+C
            pool = Pool(processes=workers, initializer=_init_worker)
            try:
                # Use small chunksize to avoid queuing too many tasks
                results = pool.imap_unordered(_process_single_image, tasks, chunksize=1)
                list(tqdm(
                    results,
                    total=len(tasks),
                    desc="Processing images",
                    unit="img"
                ))
            except KeyboardInterrupt:
                print("\n\nInterrupted by user. Terminating workers...")
                pool.terminate()  # Kill workers immediately
                pool.join()       # Wait for cleanup
                print("Cleanup complete. Exiting.")
                sys.exit(1)
            else:
                pool.close()
                pool.join()
        else:
            # Sequential processing
            for task in tqdm(tasks, desc="Processing images", unit="img"):
                if verbose:
                    tqdm.write(f"Processing: {task[0].relative_to(input_dir)}")
                _process_single_image(task)
        
        print(f"Completed processing {len(png_files)} images")
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Batch resize PNG images while preserving directory structure"
    )
    parser.add_argument(
        "input_dir",
        type=str,
        help="Input directory containing PNG files"
    )
    parser.add_argument(
        "output_dir",
        type=str,
        help="Output directory for resized images"
    )
    parser.add_argument(
        "--width",
        type=int,
        default=800,
        help="Target width in pixels (default: 800)"
    )
    parser.add_argument(
        "--height",
        type=int,
        default=600,
        help="Target height in pixels (default: 600)"
    )
    parser.add_argument(
        "--no-aspect",
        action="store_true",
        help="Don't maintain aspect ratio (stretch to exact dimensions)"
    )
    parser.add_argument(
        "-r", "--resampling",
        type=str,
        default="lanczos",
        choices=["nearest", "bilinear", "bicubic", "lanczos"],
        help="Resampling filter: nearest (sharp, for text/upsampling), bilinear, bicubic, lanczos (default, best for photos)"
    )
    parser.add_argument(
        "-q", "--quality",
        type=int,
        default=95,
        help="Output quality 1-100 (default: 95)"
    )
    parser.add_argument(
        "-j", "--workers",
        type=int,
        default=None,
        help=f"Number of parallel workers (default: {cpu_count()}, use 1 for sequential)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose progress information"
    )
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    if not input_dir.exists():
        print(f"Error: Input directory '{input_dir}' does not exist", file=sys.stderr)
        sys.exit(1)
    
    if not input_dir.is_dir():
        print(f"Error: '{input_dir}' is not a directory", file=sys.stderr)
        sys.exit(1)
    
    size = (args.width, args.height)
    maintain_aspect = not args.no_aspect
    
    # Map resampling method
    resampling_map = {
        "nearest": Image.Resampling.NEAREST,
        "bilinear": Image.Resampling.BILINEAR,
        "bicubic": Image.Resampling.BICUBIC,
        "lanczos": Image.Resampling.LANCZOS,
    }
    resampling = resampling_map[args.resampling]
    
    # Set workers (default to all CPU cores)
    workers = args.workers if args.workers is not None else cpu_count()
    
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Target size: {args.width}x{args.height}")
    print(f"Maintain aspect ratio: {maintain_aspect}")
    print(f"Resampling method: {args.resampling.upper()}")
    print(f"Parallel workers: {workers}")
    print()
    
    process_directory(
        input_dir,
        output_dir,
        size,
        maintain_aspect,
        resampling,
        args.quality,
        workers,
        args.verbose
    )


if __name__ == "__main__":
    main()