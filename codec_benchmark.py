"""
Comprehensive Codec Benchmark Script
Tests H.264, H.265, ProRes, and HAP encoding with CPU/GPU and concurrent task variations
"""

import os
import subprocess
import time
import multiprocessing
from datetime import datetime

# Codec configurations matching AutoFFmpeg
CODEC_CONFIGS = {
    'h264_nvenc': {
        'name': 'H.264 (NVENC GPU)',
        'codec': 'h264_nvenc',
        'args': ['-c:v', 'h264_nvenc', '-preset', 'p4', '-cq', '23', '-b:v', '0'],
        'container': 'mp4',
        'requires_gpu': True
    },
    'h264_cpu': {
        'name': 'H.264 (CPU)',
        'codec': 'libx264',
        'args': ['-c:v', 'libx264', '-preset', 'medium', '-crf', '23'],
        'container': 'mp4',
        'requires_gpu': False
    },
    'h265_nvenc': {
        'name': 'H.265 (NVENC GPU)',
        'codec': 'hevc_nvenc',
        'args': ['-c:v', 'hevc_nvenc', '-preset', 'p4', '-cq', '23', '-b:v', '0'],
        'container': 'mp4',
        'requires_gpu': True
    },
    'h265_cpu': {
        'name': 'H.265 (CPU)',
        'codec': 'libx265',
        'args': ['-c:v', 'libx265', '-preset', 'medium', '-crf', '23'],
        'container': 'mp4',
        'requires_gpu': False
    },
    'prores': {
        'name': 'ProRes 422 HQ',
        'codec': 'prores_ks',
        'args': ['-c:v', 'prores_ks', '-profile:v', '3', '-vendor', 'apl0', '-pix_fmt', 'yuv422p10le'],
        'container': 'mov',
        'requires_gpu': False
    },
    'hap': {
        'name': 'HAP',
        'codec': 'hap',
        'args': ['-c:v', 'hap', '-format', 'hap'],
        'container': 'mov',
        'requires_gpu': False
    }
}


def create_test_frames(output_dir, num_frames=100, resolution='1920x1080'):
    """Create test image sequence using FFmpeg"""
    print(f"\n=== Creating {num_frames} test frames ({resolution}) ===")

    os.makedirs(output_dir, exist_ok=True)

    # Generate test pattern frames (color bars with frame counter)
    cmd = [
        'ffmpeg',
        '-f', 'lavfi',
        '-i', f'testsrc=duration={num_frames/24}:size={resolution}:rate=24',
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
    chunk_num, input_pattern, output_file, start_frame, num_frames, codec_args = args

    cmd = [
        'ffmpeg',
        '-start_number', str(start_frame),
        '-i', input_pattern,
        '-frames:v', str(num_frames),
    ] + codec_args + [
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


def benchmark_codec_concurrent(test_dir, num_frames, codec_key, codec_config, concurrent_tasks):
    """Benchmark a specific codec with specified number of concurrent tasks"""
    input_pattern = f'{test_dir}/test_frame_%04d.png'

    # Calculate chunk size
    chunk_size = num_frames // concurrent_tasks
    chunks = []

    for i in range(concurrent_tasks):
        start_frame = i * chunk_size + 1  # FFmpeg frames are 1-indexed
        frames_in_chunk = chunk_size if i < concurrent_tasks - 1 else (num_frames - i * chunk_size)
        output_file = f'{test_dir}/{codec_key}_chunk_{i+1:03d}.{codec_config["container"]}'

        chunks.append((i + 1, input_pattern, output_file, start_frame, frames_in_chunk, codec_config['args']))

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

    avg_speed = 0
    if successful and any(r.get('speed') for r in successful):
        speeds = [r['speed'] for r in successful if r.get('speed')]
        avg_speed = sum(speeds) / len(speeds) if speeds else 0

    # Cleanup chunk files
    for chunk in chunks:
        output_file = chunk[2]
        if os.path.exists(output_file):
            os.remove(output_file)

    return {
        'codec': codec_key,
        'concurrent_tasks': concurrent_tasks,
        'total_time': total_time,
        'successful': len(successful),
        'failed': len(failed),
        'avg_speed': avg_speed,
        'efficiency': (num_frames / 24) / total_time if total_time > 0 else 0
    }


def check_gpu_support():
    """Check if NVIDIA GPU encoding is available"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-encoders'],
            capture_output=True,
            text=True,
            check=True
        )
        has_nvenc_h264 = 'h264_nvenc' in result.stdout
        has_nvenc_h265 = 'hevc_nvenc' in result.stdout
        return has_nvenc_h264, has_nvenc_h265
    except:
        return False, False


def main():
    print("="*70)
    print("Comprehensive Codec Benchmark - AutoFFmpeg")
    print("="*70)

    # Configuration
    test_dir = r"c:\temp\codec_benchmark"
    num_frames = 200  # ~8 seconds at 24fps - longer test for better results
    max_concurrent = min(4, multiprocessing.cpu_count())
    resolution = '1920x1080'  # Standard HD

    print(f"\nSystem Info:")
    print(f"  CPU cores: {multiprocessing.cpu_count()}")
    print(f"  Test frames: {num_frames} ({num_frames/24:.2f}s @ 24fps)")
    print(f"  Resolution: {resolution}")
    print(f"  Test directory: {test_dir}")
    print(f"  Testing concurrent tasks: 1 to {max_concurrent}")

    # Check GPU support
    has_nvenc_h264, has_nvenc_h265 = check_gpu_support()
    print(f"\nGPU Encoding Support:")
    print(f"  H.264 NVENC: {'Available' if has_nvenc_h264 else 'NOT AVAILABLE'}")
    print(f"  H.265 NVENC: {'Available' if has_nvenc_h265 else 'NOT AVAILABLE'}")

    # Filter codecs based on GPU availability
    test_codecs = {}
    for key, config in CODEC_CONFIGS.items():
        if config['requires_gpu']:
            if (key.startswith('h264') and has_nvenc_h264) or (key.startswith('h265') and has_nvenc_h265):
                test_codecs[key] = config
        else:
            test_codecs[key] = config

    if not test_codecs:
        print("\n[ERROR] No codecs available to test!")
        return

    print(f"\nTesting codecs: {', '.join([c['name'] for c in test_codecs.values()])}")

    # Create test frames
    if not create_test_frames(test_dir, num_frames, resolution):
        print("\n[ERROR] Failed to create test frames. Exiting.")
        return

    # Run benchmarks
    all_results = []

    for codec_key, codec_config in test_codecs.items():
        print(f"\n{'='*70}")
        print(f"CODEC: {codec_config['name']}")
        print(f"{'='*70}")

        codec_results = []
        for concurrent in range(1, max_concurrent + 1):
            print(f"\n  Testing {concurrent} concurrent task(s)...", end=' ')
            result = benchmark_codec_concurrent(test_dir, num_frames, codec_key, codec_config, concurrent)
            codec_results.append(result)
            all_results.append(result)

            print(f"{result['total_time']:.2f}s (speed: {result['avg_speed']:.2f}x, efficiency: {result['efficiency']:.2f}x)")

            time.sleep(1)  # Brief pause between tests

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY - ALL CODECS")
    print(f"{'='*70}")

    # Group by codec
    codecs_tested = list(test_codecs.keys())
    for codec_key in codecs_tested:
        codec_name = test_codecs[codec_key]['name']
        codec_results = [r for r in all_results if r['codec'] == codec_key]

        print(f"\n{codec_name}:")
        print(f"  {'Tasks':<8} {'Time':<10} {'Success':<10} {'Speed':<12} {'Efficiency'}")
        print(f"  {'-'*60}")

        for r in codec_results:
            print(f"  {r['concurrent_tasks']:<8} {r['total_time']:<10.2f} "
                  f"{r['successful']}/{r['concurrent_tasks']:<8} "
                  f"{r['avg_speed']:<12.2f} {r['efficiency']:.2f}x")

        # Find optimal for this codec
        successful_results = [r for r in codec_results if r['successful'] == r['concurrent_tasks']]
        if successful_results:
            optimal = min(successful_results, key=lambda x: x['total_time'])
            print(f"  OPTIMAL: {optimal['concurrent_tasks']} concurrent tasks "
                  f"({optimal['total_time']:.2f}s, {optimal['efficiency']:.2f}x efficiency)")

    # Overall recommendations
    print(f"\n{'='*70}")
    print("RECOMMENDATIONS")
    print(f"{'='*70}")

    recommendations = {}
    for codec_key in codecs_tested:
        codec_name = test_codecs[codec_key]['name']
        codec_results = [r for r in all_results if r['codec'] == codec_key]
        successful_results = [r for r in codec_results if r['successful'] == r['concurrent_tasks']]

        if successful_results:
            optimal = min(successful_results, key=lambda x: x['total_time'])
            recommendations[codec_key] = optimal['concurrent_tasks']
            print(f"\n{codec_name}:")
            print(f"  Recommended concurrent tasks: {optimal['concurrent_tasks']}")
            print(f"  Expected encoding speed: {optimal['avg_speed']:.2f}x")
            print(f"  Efficiency: {optimal['efficiency']:.2f}x realtime")

            # CPU vs GPU comparison
            if codec_key.endswith('_nvenc'):
                base_codec = codec_key.replace('_nvenc', '')
                cpu_variant = base_codec + '_cpu'
                if cpu_variant in codecs_tested:
                    cpu_results = [r for r in all_results if r['codec'] == cpu_variant]
                    cpu_successful = [r for r in cpu_results if r['successful'] == r['concurrent_tasks']]
                    if cpu_successful:
                        cpu_optimal = min(cpu_successful, key=lambda x: x['total_time'])
                        speedup = cpu_optimal['total_time'] / optimal['total_time']
                        print(f"  GPU is {speedup:.1f}x faster than CPU for {base_codec.upper()}")

    # Cleanup
    print(f"\nCleaning up test directory...")
    import shutil
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    print("[OK] Cleanup complete")

    return recommendations


if __name__ == "__main__":
    try:
        recommendations = main()
        print(f"\n{'='*70}")
        print("Benchmark complete! Use these settings in AutoFFmpeg:")
        print(f"{'='*70}")
        if recommendations:
            for codec, tasks in recommendations.items():
                print(f"  {codec}: Max concurrent tasks = {tasks}")
    except KeyboardInterrupt:
        print("\n\nBenchmark cancelled by user.")
    except Exception as e:
        print(f"\n[ERROR] Benchmark failed with error: {e}")
        import traceback
        traceback.print_exc()
