export WANDB_MODE=disabled

# train_data="\
#     ../example_data/retrieval \
#     ../example_data/sts/sts.jsonl \
#     ../example_data/classification-no_in_batch_neg \
#     ../example_data/clustering-no_in_batch_neg "
    --output_dir ./test_encoder_only_base_bge-large-en-v1.5_sd \
    --overwrite_output_dir \
    --deepspeed ../../ds_stage0.json \
    --kd_loss_type kl_div \


python build_data.py
train_data="data/"
# set large epochs and small batch size for testing
num_train_epochs=1
per_device_train_batch_size=128

# set num_gpus to 2 for testing
num_gpus=1

if [ -z "$HF_HUB_CACHE" ]; then
    export HF_HUB_CACHE="$HOME/.cache/huggingface/hub"
fi

model_args="\
    --model_name_or_path intfloat/multilingual-e5-base \
    --cache_dir $HF_HUB_CACHE \
"

data_args="\
    --train_data $train_data \
    --cache_path ~/.cache \
    --train_group_size 2 \
    --query_max_len 512 \
    --passage_max_len 512 \
    --pad_to_multiple_of 8 \
    --query_instruction_for_retrieval 'query: ' \
	--passage_instruction_for_retrieval 'passage: ' \
    --query_instruction_format '{}{}' \
	--passage_instruction_format '{}{}' \
    --same_dataset_within_batch True \
    --small_threshold 0 \
    --drop_threshold 0 \
"

training_args="\
    --learning_rate 1e-5 \
    --fp16 \
    --num_train_epochs $num_train_epochs \
    --per_device_train_batch_size $per_device_train_batch_size \
    --dataloader_drop_last True \
    --warmup_ratio 0.1 \
    --logging_steps 10 \
    --save_total_limit 4 \
    --save_strategy steps \
    --save_steps 0.25 \
	--push_to_hub True \
	--hub_model_id Ehsanl/RetNLbge_e5base \
	--push_to_hub_token \
    --negatives_cross_device \
    --temperature 0.02 \
    --sentence_pooling_method mean \
    --normalize_embeddings True \
"

cmd="torchrun --nproc_per_node $num_gpus \
    finetune.py \
    $model_args \
    $data_args \
    $training_args \
"

echo $cmd
eval $cmd
