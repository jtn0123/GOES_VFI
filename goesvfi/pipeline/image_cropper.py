"""image_cropper.py

Provides the ImageCropper class, an ImageProcessor implementation for cropping images
to a specified rectangular area in the GOES_VFI pipeline.
"""

from typing import Any, Dict, Tuple, cast

from numpy import ndarray

from .image_processing_interfaces import ImageData, ImageProcessor


class ImageCropper(ImageProcessor):
    """ImageProcessor implementation for cropping images to a specified area.

    This class provides a crop method that extracts a rectangular region from an image.
    """

    def crop(self, image_data: ImageData, crop_area: tuple[int, int, int, int]) -> ImageData:
        """Crop the image data to the specified rectangular area.

        Args:
            pass
            image_data (ImageData): The input ImageData object.
            crop_area (Tuple[int, int, int, int]): A tuple (left, top, right, bottom)
            representing the crop area in pixel coordinates.

        Returns:
            ImageData: A new ImageData object with the cropped image data and updated metadata.

        Raises:
            ValueError: If the crop area is invalid for the image dimensions.
        """
        left, top, right, bottom = crop_area
        # Assume image_data.image_data is a numpy array for cropping
        image_array = cast(ndarray[Any, Any], image_data.image_data)
        height, width = image_array.shape[:2]

        # Validate crop area
        if not (0 <= left < right <= width and 0 <= top < bottom <= height):
            raise ValueError(f"Invalid crop area: {crop_area} for image dimensions {width}x{height}")

        # Perform crop
        cropped_array = image_array[top:bottom, left:right]

        # Create new ImageData object
        new_metadata: dict[str, Any] = image_data.metadata.copy()
        new_metadata["width"] = cropped_array.shape[1]
        new_metadata["height"] = cropped_array.shape[0]

        # Update processing steps
        if "processing_steps" not in new_metadata:
            new_metadata["processing_steps"] = []
        new_metadata["processing_steps"].append({"operation": "crop", "area": crop_area})

        return ImageData(image_data=cropped_array, metadata=new_metadata)

    def load(self, source_path: str) -> ImageData:
        """Not implemented. ImageCropper does not support loading images.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("ImageCropper does not implement load.")

    def process(self, image_data: ImageData, **kwargs: Any) -> ImageData:
        """Not implemented. ImageCropper does not support processing images.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("ImageCropper does not implement process.")

    def save(self, image_data: ImageData, destination_path: str) -> None:
        """Not implemented. ImageCropper does not support saving images.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("ImageCropper does not implement save.")
