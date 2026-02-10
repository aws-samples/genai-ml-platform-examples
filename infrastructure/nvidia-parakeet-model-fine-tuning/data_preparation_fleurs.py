import json
import os
import soundfile as sf
import argparse
from pathlib import Path
from tqdm import tqdm
from datasets import load_dataset

def process_fleurs_dataset(split_name, output_dir, audio_dir, full_dataset=None):
    """Process FLEURS dataset split and create manifest."""
    print(f"Processing FLEURS French {split_name} split...")
    if full_dataset is None:
        full_dataset = load_dataset('google/fleurs', 'fr_fr', revision='d7c758a6dceecd54a98cac43404d3d576e721f07')
    dataset = full_dataset[split_name]
    
    manifest_entries = []
    audio_output_dir = Path(audio_dir) / split_name
    audio_output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Processing {len(dataset)} samples...")
    for idx, sample in enumerate(tqdm(dataset, desc=f"Processing {split_name}")):
        audio_data = sample['audio']
        text = sample['transcription']
        
        # Save audio file
        audio_filename = f"{split_name}_{idx:06d}.wav"
        audio_path = audio_output_dir / audio_filename
        
        # Write audio as 16kHz mono WAV
        sf.write(audio_path, audio_data['array'], audio_data['sampling_rate'])
        
        # Get duration
        duration = len(audio_data['array']) / audio_data['sampling_rate']
        
        # Create manifest entry
        manifest_entries.append({
            "audio_filepath": str(audio_path),
            "text": text,
            "duration": duration
        })
    
    # Write manifest
    manifest_path = Path(output_dir) / f"{split_name}_manifest.jsonl"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        for entry in manifest_entries:
            f.write(json.dumps(entry) + '\n')
    
    print(f"Created {manifest_path} with {len(manifest_entries)} entries")
    return manifest_path

def main():
    parser = argparse.ArgumentParser(description='Prepare FLEURS French dataset for NeMo ASR')
    parser.add_argument('--output_dir', '-o', default='/home/ubuntu/dataset/fleurs_french',
                       help='Output directory for manifests')
    parser.add_argument('--audio_dir', '-a', default='/home/ubuntu/dataset/fleurs_french/audio',
                       help='Directory to save audio files')
    
    args = parser.parse_args()
    
    # Create output directories
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    Path(args.audio_dir).mkdir(parents=True, exist_ok=True)
    
    print("Starting FLEURS French dataset preparation...")
    print("Loading full dataset...")
    full_dataset = load_dataset('google/fleurs', 'fr_fr', revision='d7c758a6dceecd54a98cac43404d3d576e721f07')
    
    # Process each split
    train_manifest = process_fleurs_dataset('train', args.output_dir, args.audio_dir, full_dataset)
    val_manifest = process_fleurs_dataset('validation', args.output_dir, args.audio_dir, full_dataset)
    test_manifest = process_fleurs_dataset('test', args.output_dir, args.audio_dir, full_dataset)
    
    print("\n=== Dataset preparation completed! ===")
    print(f"Train manifest: {train_manifest}")
    print(f"Validation manifest: {val_manifest}")
    print(f"Test manifest: {test_manifest}")

if __name__ == "__main__":
    main()
