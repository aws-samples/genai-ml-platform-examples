#!/bin/bash

# Set script to exit on error
set -e

# Check if dialog is installed
if ! command -v dialog &> /dev/null; then
    echo "This script requires the 'dialog' utility."
    echo "Please install it with: sudo apt-get install dialog (Debian/Ubuntu)"
    echo "Or: sudo yum install dialog (CentOS/RHEL)"
    exit 1
fi

# Pink theme for dialog - setup first
export DIALOGRC=$(mktemp)
cat > "$DIALOGRC" << 'EOF'
screen_color = (magenta,black,on)
dialog_color = (black,magenta,off)
title_color = (black,magenta,on)
border_color = (black,magenta,on)
button_active_color = (black,cyan,on)
button_inactive_color = (black,magenta,off)
button_key_active_color = (black,cyan,on)
button_key_inactive_color = (black,magenta,off)
button_label_active_color = (black,cyan,on)
button_label_inactive_color = (black,magenta,off)
inputbox_color = (black,magenta,off)
inputbox_border_color = (black,magenta,on)
searchbox_color = (black,magenta,off)
searchbox_title_color = (black,magenta,on)
searchbox_border_color = (black,magenta,on)
position_indicator_color = (black,magenta,on)
menubox_color = (black,magenta,off)
menubox_border_color = (black,magenta,on)
item_color = (black,magenta,off)
item_selected_color = (black,cyan,on)
EOF

# Function to validate if input is a positive integer
is_positive_integer() {
    [[ $1 =~ ^[0-9]+$ ]] && [ "$1" -gt 0 ]
}
# Function for yes/no questions with pink background
TEMPFILE=$(mktemp)

# Get the selection
ANSWER=$?
SELECTION=""
if [ $ANSWER -eq 0 ]; then
    SELECTION=$(dialog --stdout --colors \
                --backtitle "Run Build Configuration" \
                --title "\Z1\ZbSetup Question\Zn" \
                --menu "Did you download and preprocess the dataset?" 10 60 2 \
                "Yes" "Proceed with configuration" \
                "No" "Exit")
fi

# Check what was selected
if [ "$ANSWER" -ne 0 ] || [ "$SELECTION" = "No" ]; then
    # Show warning message in a dialog box with OK button
    dialog --colors \
           --title "\Z1\ZbWARNING\Zn" \
           --ok-label "Exit" \
           --msgbox "\n\Z1You should run the download-and-prepare-data.sh script and update the path to the data in the config file.\Zn\n\nPlease run the following steps before proceeding:\n\n1. Execute: ./download-and-prepare-data.sh\n2. Verify that the paths in the config file match your data location" 15 65
    
    # Clean up and exit
    rm -f "$DIALOGRC"
    clear
    echo "Exiting: Please run download-and-prepare-data.sh first."
    exit 1
fi



# Define config file path
CONFIG_FILE="./configs/fine_tuning_config.yaml"

# Create a temporary file for storing the selection
STRATEGY_FILE="/tmp/strategy_selection.$$"
touch "$STRATEGY_FILE"

# Second question - Training strategy selection
dialog --title 'Select Training Strategy' \
       --menu 'Choose the training strategy to use:' 15 60 2 \
       'DDP' 'Distributed Data Parallel' \
       'DeepSpeed' 'DeepSpeed with ZeRO optimization' \
       2> "$STRATEGY_FILE"

# Check if user cancelled
if [ $? -ne 0 ]; then
    rm -f "$STRATEGY_FILE"
    rm -f "$DIALOGRC"
    clear
    echo "Selection cancelled. Exiting."
    exit 1
fi

# Get the selected strategy
STRATEGY=$(cat "$STRATEGY_FILE")
rm -f "$STRATEGY_FILE"

# Third question - Batch size selection
BATCH_SIZE_FILE="/tmp/batch_size.$$"

while true; do
    dialog --title 'Set Batch Size' \
           --inputbox 'Enter the batch size to use (positive integer):' 10 60 '3' \
           2> "$BATCH_SIZE_FILE"
    
    # Check if user cancelled
    if [ $? -ne 0 ]; then
        rm -f "$BATCH_SIZE_FILE"
        rm -f "$DIALOGRC"
        clear
        echo "Selection cancelled. Exiting."
        exit 1
    fi
    
    BATCH_SIZE=$(cat "$BATCH_SIZE_FILE")
    
    # Validate the batch size
    if is_positive_integer "$BATCH_SIZE"; then
        break
    else
        dialog --colors --msgbox "\Z1Invalid batch size. Please enter a positive integer.\Zn" 8 50
    fi
done

rm -f "$BATCH_SIZE_FILE"

# Fourth question - Max epochs selection
EPOCHS_FILE="/tmp/max_epochs.$$"

while true; do
    dialog --title 'Set Maximum Epochs' \
           --inputbox 'Enter the maximum number of training epochs:' 10 60 '40' \
           2> "$EPOCHS_FILE"
    
    # Check if user cancelled
    if [ $? -ne 0 ]; then
        rm -f "$EPOCHS_FILE"
        rm -f "$DIALOGRC"
        clear
        echo "Selection cancelled. Exiting."
        exit 1
    fi
    
    MAX_EPOCHS=$(cat "$EPOCHS_FILE")
    
    # Validate the max epochs
    if is_positive_integer "$MAX_EPOCHS"; then
        break
    else
        dialog --colors --msgbox "\Z1Invalid max epochs. Please enter a positive integer.\Zn" 8 50
    fi
done

rm -f "$EPOCHS_FILE"

# Create a backup of the config file
cp "$CONFIG_FILE" "${CONFIG_FILE}.bak"

# Update all batch sizes in the config file - specifically for train_ds, validation_ds, and test_ds
sed -i "/model:/,/trainer:/ s/batch_size: [0-9]\+/batch_size: $BATCH_SIZE/g" "$CONFIG_FILE"

# Update max_epochs in the trainer section
sed -i "/trainer:/,/exp_manager:/ s/max_epochs: [0-9]\+/max_epochs: $MAX_EPOCHS/g" "$CONFIG_FILE"

# Update the config file based on selected strategy
if [ "$STRATEGY" == "DDP" ]; then
    # Update config for DDP strategy
    sed -i '/strategy:/,/gradient_clip_val:/ {
        s/_target_: "lightning.pytorch.strategies.DeepSpeedStrategy"/_target_: "lightning.pytorch.strategies.DDPStrategy"/
        # Remove any stage line completely (with or without comment)
        /stage:/d
    }' "$CONFIG_FILE"
    
    # Also update the trainer_strategy section if it exists
    if grep -q "trainer_strategy:" "$CONFIG_FILE"; then
        sed -i '/trainer_strategy:/,/^[a-z]/ s/strategy: .*$/strategy: ddp/' "$CONFIG_FILE"
    fi
    
    dialog --colors --msgbox "\Z2Config file updated successfully with:\n- DDP training strategy\n- Batch size: $BATCH_SIZE\n- Max epochs: $MAX_EPOCHS\Zn" 12 60
    
elif [ "$STRATEGY" == "DeepSpeed" ]; then
    # Update config for DeepSpeed strategy with stage 2
    sed -i '/strategy:/,/gradient_clip_val:/ {
        s/_target_: "lightning.pytorch.strategies.DDPStrategy"/_target_: "lightning.pytorch.strategies.DeepSpeedStrategy"/
        # Remove any existing stage line
        /stage:/d
    }' "$CONFIG_FILE"
    
    # Add stage: 2 line right after the _target_ line
    sed -i '/_target_: "lightning.pytorch.strategies.DeepSpeedStrategy"/a \    stage: 2' "$CONFIG_FILE"
    
    # Also update the trainer_strategy section if it exists
    if grep -q "trainer_strategy:" "$CONFIG_FILE"; then
        sed -i '/trainer_strategy:/,/^[a-z]/ s/strategy: .*$/strategy: deepspeed/' "$CONFIG_FILE"
    fi
    
    dialog --colors --msgbox "\Z2Config file updated successfully with:\n- DeepSpeed training strategy\n- Stage: 2\n- Batch size: $BATCH_SIZE\n- Max epochs: $MAX_EPOCHS\Zn" 14 60
fi

# Cleanup dialog configuration
rm -f "$DIALOGRC"
clear

# Success message
echo "All checks passed. Configuration set to:"
echo "- Training strategy: $STRATEGY"
echo "- Batch size: $BATCH_SIZE"
echo "- Max epochs: $MAX_EPOCHS"
echo "Starting training script..."

# Run the training script
sh ./run-train.sh
