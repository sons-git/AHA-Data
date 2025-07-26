import asyncio
from transformers import pipeline


class Classifier:
    """Classifier for text, general images, and disease-related images using zero-shot models."""

    def __init__(self, config: dict = None):
        self.config = config
        self.candidate_labels = self.config["candidate_labels"]
        self.zero_shot_text_classification = pipeline(
            "zero-shot-classification", 
            model="facebook/bart-large-mnli"
        )

    async def classify_text(self, prompt: str = None) -> str:
        """
        Classify a text prompt using zero-shot classification.

        This function uses a zero-shot text classification model to determine the most appropriate
        label from a predefined list (`self.candidate_labels`), such as ["not-medical-related", "dermatology",...].

        Args:
            prompt (str, optional): The input text to be classified.

        Returns:
            str: The top predicted label based on the input text.
        """
        result = await asyncio.to_thread(
            self.zero_shot_text_classification,
            prompt,
            candidate_labels=self.candidate_labels
        )
        return result["labels"][0]