import torch
import asyncio
import numpy as np
from typing import List, Tuple
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForMaskedLM, AutoTokenizer

_model_d = None
_model_s_tokenizer = None
_model_s_embedder = None

def get_dense_embedder():
    """
    Load and return a singleton instance of a dense embedder model.

    Uses the `intfloat/multilingual-e5-small` model from SentenceTransformers
    to generate dense embeddings. Ensures the model is loaded only once
    and reused across function calls.

    Returns:
        SentenceTransformer: An instance of the dense embedding model.
    """
    global _model_d
    if _model_d is None:
        print("Loading dense embedder model...")
        _model_d = SentenceTransformer("intfloat/multilingual-e5-small")
    return _model_d

def get_sparse_embedder_and_tokenizer():
    """
    Load and return singleton instances of a sparse embedder model and its tokenizer.

    Uses the `naver/splade-cocondenser-ensembledistil` model from Hugging Face
    to compute sparse vector representations via masked language modeling.

    Returns:
        Tuple[PreTrainedTokenizer, PreTrainedModel]: The tokenizer and the embedder model.
    """
    global _model_s_tokenizer, _model_s_embedder
    if _model_s_tokenizer is None or _model_s_embedder is None:
        print("Loading sparse embedder model and tokenizer...")
        _model_s_tokenizer = AutoTokenizer.from_pretrained("naver/splade-cocondenser-ensembledistil")
        _model_s_embedder = AutoModelForMaskedLM.from_pretrained("naver/splade-cocondenser-ensembledistil")
    return _model_s_tokenizer, _model_s_embedder

async def compute_dense_vector(text: str = None) -> List[float] | np.ndarray:
    """
    Convert input text into a dense embedding vector.

    Uses the SentenceTransformer model to produce a dense numerical vector
    that captures the semantic content of the input text.

    Args:
        text (str, optional): The input text to embed.

    Returns:
        List[float] | np.ndarray: A dense vector representation of the input text.
    """
    embedder = get_dense_embedder()
    embedded_text = embedder.encode(text)
    return embedded_text

async def compute_sparse_vector(text: str = None) -> Tuple[List[int], List[float]]:
    """
    Convert input text into a sparse vector using SPLADE technique.

    Tokenizes the input text and passes it through a masked language model,
    then computes a sparse vector using a combination of ReLU, log, and max-pooling
    over the logits. Only non-zero indices and their values are returned.

    Args:
        text (str, optional): The input text to embed.

    Returns:
        Tuple[List[int], List[float]]: A tuple containing:
            - indices (List[int]): Positions of non-zero values in the sparse vector.
            - values (List[float]): Corresponding non-zero values at those indices.
    """
    tokenizer, embedder = get_sparse_embedder_and_tokenizer()
    tokens = tokenizer(text, return_tensors="pt")
    output = embedder(**tokens)
    logits, attention_mask = output.logits, tokens.attention_mask
    relu_log = torch.log(1 + torch.relu(logits))
    weighted_log = relu_log * attention_mask.unsqueeze(-1)
    max_val, _ = torch.max(weighted_log, dim=1)
    vec = max_val.squeeze()

    # Safely get indices of non-zero values
    indices = torch.nonzero(vec, as_tuple=True)[0].tolist()

    if isinstance(indices, int):  # if single int, convert to list
            indices = [indices]

    # Safely get corresponding values
    values = vec[indices].tolist() if indices else []

    return indices, values

async def embed(text: str) -> tuple[list[float], list[int], list[float]]:
    """
    Generate dense and sparse embeddings for a given text.
    Returns:
        dense_vec: List of floats representing dense embedding
        indices: List of ints for sparse embedding indices
        values: List of floats for sparse embedding values
    """
    try:
        dense_vec, (indices, values) = await asyncio.gather(
            compute_dense_vector(text),
            compute_sparse_vector(text)
        )
        return dense_vec, indices, values
    except Exception as e:
        print(f"[Embedding Error] Failed to embed text: {text}. Error: {e}")
        return [], [], []