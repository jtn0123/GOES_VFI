"""image_cropper.py.

Provides the ImageCropper class, an ImageProcessor implementation for cropping images
to a specified rectangular area in the GOES_VFI pipeline.
"""

from typing import Any, cast

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
        image_array = cast("ndarray[Any, Any]", image_data.image_data)
        height, width = image_array.shape[:2]

        # Validate crop area
        if not (0 <= left < right <= width and 0 <= top < bottom <= height):
            msg = f"Invalid crop area: {crop_area} for image dimensions {width}x{height}"
            raise ValueError(msg)

        # Perform crop - make a copy to ensure independence from original
        cropped_array = image_array[top:bottom, left:right].copy()

        # Create new ImageData object
        new_metadata: dict[str, Any] = image_data.metadata.copy()
        new_metadata["width"] = cropped_array.shape[1]
        new_metadata["height"] = cropped_array.shape[0]
        new_metadata["crop_rect"] = crop_area

        # Update processing steps
        if "processing_steps" not in new_metadata:
            new_metadata["processing_steps"] = []
        new_metadata["processing_steps"].append({"operation": "crop", "area": crop_area})

        return ImageData(image_data=cropped_array, metadata=new_metadata)

    def load(self, source_path: str) -> ImageData:
        """Load image data from a numpy file.

        Args:
            source_path (str): Path to the numpy file to load.

        Returns:
            ImageData: Loaded image data with metadata.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file cannot be loaded as an image.
        """
        from pathlib import Path

        import numpy as np

        path = Path(source_path)
        if not path.exists():
            msg = f"File not found: {source_path}"
            raise FileNotFoundError(msg)

        try:
            image_array = np.load(source_path)
            if image_array.ndim < 2:
                msg = f"Invalid image dimensions: {image_array.ndim}"
                raise ValueError(msg)

            metadata: dict[str, Any] = {
                "filename": path.name,
                "width": image_array.shape[1],
                "height": image_array.shape[0],
            }

            if image_array.ndim == 3:
                metadata["channels"] = image_array.shape[2]

            return ImageData(image_data=image_array, metadata=metadata)
        except Exception as e:
            msg = f"Failed to load image: {e}"
            raise ValueError(msg) from e

    def process(self, image_data: ImageData | dict[str, Any], **kwargs: Any) -> ImageData | dict[str, Any]:
        """Process image data based on provided parameters.

        This method can be called in two ways:
        1. With a params dict directly: process(params)
        2. With ImageData and kwargs: process(image_data, **kwargs)

        Args:
            image_data: Either ImageData or params dict with:
                - input_path: Path to input numpy file
                - output_path: Path to save output numpy file
                - crop_rect: Tuple of (left, top, right, bottom)
            **kwargs: Additional parameters (not used in pipeline mode)

        Returns:
            ImageData or dict: Result dictionary with success status when params provided.
        """
        # Check if this is being called with params dict
        if isinstance(image_data, dict):
            params = image_data

            result = {"success": False, "error": None}

            # Validate parameters
            required_keys = {"input_path", "output_path", "crop_rect"}
            if not all(key in params for key in required_keys):
                result["error"] = f"Missing required parameters. Need: {required_keys}"
                return result

            try:
                # Load input image
                loaded_data = self.load(params["input_path"])

                # Crop the image
                cropped_data = self.crop(loaded_data, params["crop_rect"])

                # Save the cropped image
                self.save(cropped_data, params["output_path"])

                result["success"] = True
                result["output_path"] = params["output_path"]

            except Exception as e:
                result["error"] = str(e)

            return result

        # Original interface - not implemented
        msg = "ImageCropper.process() with ImageData not implemented"
        raise NotImplementedError(msg)

    def save(self, image_data: ImageData, destination_path: str) -> None:
        """Save image data to a numpy file.

        Args:
            image_data (ImageData): The image data to save.
            destination_path (str): Path where to save the numpy file.

        Raises:
            IOError: If the file cannot be saved.
        """
        import numpy as np

        try:
            np.save(destination_path, image_data.image_data)
        except Exception as e:
            msg = f"Failed to save image: {e}"
            raise OSError(msg) from e
