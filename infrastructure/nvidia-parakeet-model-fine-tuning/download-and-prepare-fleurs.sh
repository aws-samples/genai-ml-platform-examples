#!/bin/bash
set -e

# Terminal colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR=$(pwd)
CONFIG_FILE="$SCRIPT_DIR/configs/fine_tuning_config.yaml"
DATA_DIR="/home/ubuntu/dataset/fleurs_french"
AUDIO_DIR="$DATA_DIR/audio"

echo -e "${BLUE}${BOLD}[STEP]${NC} Creating directories..."
mkdir -p "$DATA_DIR"
mkdir -p "$AUDIO_DIR"

echo -e "${BLUE}${BOLD}[STEP]${NC} Clearing cache..."
rm -rf /home/ubuntu/.cache/huggingface/datasets/google___fleurs

echo -e "${BLUE}${BOLD}[STEP]${NC} Downloading and preparing FLEURS French dataset..."
python data_preparation_fleurs.py --output_dir="$DATA_DIR" --audio_dir="$AUDIO_DIR"



# Define manifest paths
TRAIN_MANIFEST="$DATA_DIR/train_manifest.jsonl"
VAL_MANIFEST="$DATA_DIR/validation_manifest.jsonl"
TEST_MANIFEST="$DATA_DIR/test_manifest.jsonl"

echo -e "${BLUE}${BOLD}[STEP]${NC} Updating configuration file..."
cp "$CONFIG_FILE" "${CONFIG_FILE}.bak"

sed -i "s|train_manifest: \".*\"|train_manifest: \"$TRAIN_MANIFEST\"|g" "$CONFIG_FILE"
sed -i "s|validation_manifest: \".*\"|validation_manifest: \"$VAL_MANIFEST\"|g" "$CONFIG_FILE"
sed -i "s|test_manifest: \".*\"|test_manifest: \"$TEST_MANIFEST\"|g" "$CONFIG_FILE"
sed -i "s|name: \".*\"|name: \"French_ASR_Parakeet_Finetuning\"|g" "$CONFIG_FILE"

echo -e "${GREEN}${BOLD}[SUCCESS]${NC} FLEURS French dataset preparation completed!"
echo -e "${CYAN}${BOLD}[INFO]${NC} Train manifest: $TRAIN_MANIFEST"
echo -e "${CYAN}${BOLD}[INFO]${NC} Validation manifest: $VAL_MANIFEST"
echo -e "${CYAN}${BOLD}[INFO]${NC} Test manifest: $TEST_MANIFEST"
