"""
ProRes Encoding Benchmark Script
Tests different concurrent task counts to find optimal performance
"""

import os
import subprocess
import time
import multiprocessing
from datetime import datetime

def create_test_frames(output_dir, num_frames=100):
    """Create test image sequence using FFmpeg"""
    print(f"\n=== Creating {num_frames} test frames ===")

    os.makedirs(output_dir, exist_ok=True)

    # Generate test pattern frames (color bars with frame counter)
    cmd = [
        'ffmpeg',
        '-f', 'lavfi',
        '-i', f'testsrc=duration={num_frames/24}:size=1920x1080:rate=24',
        '-frames:v', str(num_frames),
        f'{output_dir}/test_frame_%04d.png',
        '-y'
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"[OK] Created {num_frames} test frames in {output_dir}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to create test frames: {e.stderr.decode()}")
        return False


def encode_chunk(args):
    """Encode a single chunk - used for parallel processing"""
    chunk_num, input_pattern, output_file, start_frame, num_frames = args

    cmd = [
        'ffmpeg',
        '-start_number', str(start_frame),
        '-i', input_pattern,
        '-frames:v', str(num_frames),
        '-c:v', 'prores_ks',
        '-profile:v', '3',  # ProRes 422 HQ
        '-vendor', 'apl0',
        '-pix_fmt', 'yuv422p10le',
        output_file,
        '-y'
    ]

    start_time = time.time()
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        end_time = time.time()
        elapsed = end_time - start_time

        # Extract encoding speed from FFmpeg output
        speed = None
        for line in result.stderr.split('\n'):
            if 'speed=' in line:
                try:
                    speed_str = line.split('speed=')[1].split('x')[0].strip()
                    speed = float(speed_str)
                except:
                    pass

        return {
            'chunk': chunk_num,
            'success': True,
            'time': elapsed,
            'speed': speed
        }
    except subprocess.CalledProcessError as e:
        end_time = time.time()
        return {
            'chunk': chunk_num,
            'success': False,
            'time': end_time - start_time,
            'error': str(e)
        }


def benchmark_concurrent_tasks(test_dir, num_frames, concurrent_tasks):
    """Benchmark encoding with specified number of concurrent tasks"""
    print(f"\n{'='*60}")
    print(f"Testing with {concurrent_tasks} concurrent task(s)")
    print(f"{'='*60}")

    input_pattern = f'{test_dir}/test_frame_%04d.png'

    # Calculate chunk size
    chunk_size = num_frames // concurrent_tasks
    chunks = []

    for i in range(concurrent_tasks):
        start_frame = i * chunk_size + 1  # FFmpeg frames are 1-indexed
        frames_in_chunk = chunk_size if i < concurrent_tasks - 1 else (num_frames - i * chunk_size)
        output_file = f'{test_dir}/benchmark_chunk_{i+1:03d}.mov'

        chunks.append((i + 1, input_pattern, output_file, start_frame, frames_in_chunk))

    # Run encoding
    start_time = time.time()

    if concurrent_tasks == 1:
        # Single task - run directly
        results = [encode_chunk(chunks[0])]
    else:
        # Multiple tasks - use multiprocessing
        with multiprocessing.Pool(processes=concurrent_tasks) as pool:
            results = pool.map(encode_chunk, chunks)

    end_time = time.time()
    total_time = end_time - start_time

    # Analyze results
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    print(f"\nResults:")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Successful chunks: {len(successful)}/{len(chunks)}")
    print(f"  Failed chunks: {len(failed)}")

    if successful:
        avg_speed = sum(r['speed'] for r in successful if r['speed']) / len([r for r in successful if r['speed']])
        print(f"  Average encoding speed: {avg_speed:.3f}x")
        print(f"  Efficiency: {(num_frames / 24) / total_time:.3f}x realtime")

    # Cleanup chunk files
    for chunk in chunks:
        output_file = chunk[2]
        if os.path.exists(output_file):
            os.remove(output_file)

    return {
        'concurrent_tasks': concurrent_tasks,
        'total_time': total_time,
        'successful': len(successful),
        'failed': len(failed),
        'avg_speed': avg_speed if successful else 0,
        'efficiency': (num_frames / 24) / total_time if total_time > 0 else 0
    }


def main():
    print("="*60)
    print("ProRes Encoding Benchmark")
    print("="*60)

    # Configuration
    test_dir = r"c:\temp\prores_benchmark"
    num_frames = 100  # ~4 seconds at 24fps
    max_concurrent = min(4, multiprocessing.cpu_count())  # Test up to 4 or CPU count

    print(f"\nSystem Info:")
    print(f"  CPU cores: {multiprocessing.cpu_count()}")
    print(f"  Test frames: {num_frames} ({num_frames/24:.2f}s @ 24fps)")
    print(f"  Test directory: {test_dir}")
    print(f"  Testing concurrent tasks: 1 to {max_concurrent}")

    # Create test frames
    if not create_test_frames(test_dir, num_frames):
        print("\n[ERROR] Failed to create test frames. Exiting.")
        return

    # Run benchmarks
    results = []
    for concurrent in range(1, max_concurrent + 1):
        result = benchmark_concurrent_tasks(test_dir, num_frames, concurrent)
        results.append(result)
        time.sleep(2)  # Brief pause between tests

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"\n{'Tasks':<8} {'Time':<10} {'Success':<10} {'Speed':<12} {'Efficiency'}")
    print(f"{'-'*60}")

    for r in results:
        print(f"{r['concurrent_tasks']:<8} {r['total_time']:<10.2f} "
              f"{r['successful']}/{r['concurrent_tasks']:<8} "
              f"{r['avg_speed']:<12.3f} {r['efficiency']:.3f}x")

    # Determine optimal
    # Best is fastest total time with all chunks successful
    successful_results = [r for r in results if r['successful'] == r['concurrent_tasks']]

    if successful_results:
        optimal = min(successful_results, key=lambda x: x['total_time'])
        print(f"\n{'='*60}")
        print(f"RECOMMENDATION: {optimal['concurrent_tasks']} concurrent task(s)")
        print(f"{'='*60}")
        print(f"  Fastest total time: {optimal['total_time']:.2f}s")
        print(f"  Encoding efficiency: {optimal['efficiency']:.3f}x realtime")
        print(f"\nThis will be set as the maximum for ProRes encoding.")

        # Cleanup
        print(f"\nCleaning up test directory...")
        import shutil
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
        print("[OK] Cleanup complete")

        return optimal['concurrent_tasks']
    else:
        print("\n[ERROR] All tests had failures. Recommend using 1 concurrent task.")
        return 1


if __name__ == "__main__":
    try:
        optimal_tasks = main()
    except KeyboardInterrupt:
        print("\n\nBenchmark cancelled by user.")
    except Exception as e:
        print(f"\n[ERROR] Benchmark failed with error: {e}")
        import traceback
        traceback.print_exc()
