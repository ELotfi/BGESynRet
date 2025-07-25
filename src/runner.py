import logging
from typing import Tuple
from transformers import (
    AutoModel, AutoConfig,
    AutoTokenizer, PreTrainedTokenizer
)
import torch
from peft import LoraConfig, TaskType, get_peft_model
from .absm import AbsEmbedderRunner, AbsEmbedderModel, EmbedderTrainerCallbackForDataRefresh
from .modeling import BiEncoderOnlyEmbedderModel
from .trainer import EncoderOnlyEmbedderTrainer

logger = logging.getLogger(__name__)


class EncoderOnlyEmbedderRunner(AbsEmbedderRunner):
    """
    Finetune Runner for base embedding models.
    """
    def load_tokenizer_and_model(self) -> Tuple[PreTrainedTokenizer, AbsEmbedderModel]:
        """Load tokenizer and model.

        Returns:
            Tuple[PreTrainedTokenizer, AbsEmbedderModel]: Tokenizer and model instances.
        """
        tokenizer = AutoTokenizer.from_pretrained(
            self.model_args.model_name_or_path,
            cache_dir=self.model_args.cache_dir,
            token=self.model_args.token,
            trust_remote_code=self.model_args.trust_remote_code
        )
        base_model = AutoModel.from_pretrained(
            self.model_args.model_name_or_path,
            cache_dir=self.model_args.cache_dir,
            token=self.model_args.token,
            trust_remote_code=self.model_args.trust_remote_code,
            attn_implementation = 'flash_attention_2' if self.model_args.use_flash_attention else None,
            torch_dtype = torch.bfloat16 if self.model_args.load_bf16 else 'auto'
        )

        num_labels = 1
        config = AutoConfig.from_pretrained(
            self.model_args.config_name if self.model_args.config_name else self.model_args.model_name_or_path,
            num_labels=num_labels,
            cache_dir=self.model_args.cache_dir,
            token=self.model_args.token,
            trust_remote_code=self.model_args.trust_remote_code,
        )
        logger.info('Config: %s', config)
        if self.model_args.add_lora:
        # peft config and wrapping
            print('adding lora ...')
            peft_config = LoraConfig(
                r=self.model_args.lora_rank,
                lora_alpha=self.model_args.lora_alpha,
                bias="none",
                task_type=TaskType.FEATURE_EXTRACTION,
                target_modules=["q_proj", "v_proj", "k_proj", "o_proj", "down_proj", "up_proj", "gate_proj"],
                inference_mode=False
            )
            base_model = get_peft_model(base_model, peft_config)
            base_model.print_trainable_parameters()

        model = BiEncoderOnlyEmbedderModel(
            base_model,
            tokenizer=tokenizer,
            negatives_cross_device=self.training_args.negatives_cross_device,
            temperature=self.training_args.temperature,
            sub_batch_size=self.training_args.sub_batch_size,
            kd_loss_type=self.training_args.kd_loss_type,
            sentence_pooling_method=self.training_args.sentence_pooling_method,
            normalize_embeddings=self.training_args.normalize_embeddings
        )

        if self.training_args.gradient_checkpointing:
            model.enable_input_require_grads()

        if self.training_args.fix_position_embedding:
            for k, v in model.named_parameters():
                if "position_embeddings" in k:
                    logging.info(f"Freeze the parameters for {k}")
                    v.requires_grad = False
        return tokenizer, model

    def load_trainer(self) -> EncoderOnlyEmbedderTrainer:
        """Load the trainer.

        Returns:
            EncoderOnlyEmbedderTrainer: Loaded trainer instance.
        """
        trainer = EncoderOnlyEmbedderTrainer(
            model=self.model,
            args=self.training_args,
            train_dataset=self.train_dataset,
            data_collator=self.data_collator,
            tokenizer=self.tokenizer
        )
        if self.data_args.same_dataset_within_batch:
            trainer.add_callback(EmbedderTrainerCallbackForDataRefresh(self.train_dataset))
        return trainer
