"""image_processing_interfaces.py.

Defines abstract interfaces and data structures for image processing pipeline components
in the GOES_VFI application. Provides a standard for how image data and processing steps
are represented and interacted with, enabling modular and extensible pipeline design.
"""

import abc
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np  # Import numpy
from PIL import Image  # Import PIL.Image

# Define ImageType as a type alias
if TYPE_CHECKING:
    # Use np.ndarray with type parameters for static analysis
    type ImageType = Image.Image | np.ndarray[Any, Any]
else:
    # Use a more general type at runtime if numpy isn't strictly typed or for fallback
    # np is already imported at the top of the file
    type ImageType = Image.Image | np.ndarray


@dataclass
class ImageData:
    """Container for image data and associated metadata in the processing pipeline.

    Attributes:
        image_data (ImageType): The core image pixel data (e.g., a NumPy array).
        source_path (Optional[str]): The original file path of the image, if applicable.
        metadata (Dict[str, Any]): Arbitrary metadata (e.g., dimensions, format,)
        processing history, timestamps, geospatial info).
    """

    image_data: ImageType
    source_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def height(self) -> int | None:
        """Returns the height of the image if available in metadata or image_data.

        Returns:
            Optional[int]: The height of the image, or None if unavailable.
        """
        if "height" in self.metadata and isinstance(self.metadata["height"], int):
            return self.metadata["height"]
        if hasattr(self.image_data, "shape") and len(self.image_data.shape) >= 2:
            return int(self.image_data.shape[0])
        return None

    @property
    def width(self) -> int | None:
        """Returns the width of the image if available in metadata or image_data.

        Returns:
            Optional[int]: The width of the image, or None if unavailable.
        """
        if "width" in self.metadata and isinstance(self.metadata["width"], int):
            return self.metadata["width"]
        if hasattr(self.image_data, "shape") and len(self.image_data.shape) >= 2:
            return int(self.image_data.shape[1])
        return None

    def update_metadata(self, new_meta: dict[str, Any]) -> None:
        """Update the metadata dictionary with new values.

        Args:
            new_meta (Dict[str, Any]): New metadata to merge into the existing dictionary.
        """
        self.metadata.update(new_meta)


class ImageProcessor(abc.ABC):
    """Abstract base class for image processing pipeline components.

    This interface standardizes how different processing steps (loading,)
    reprojection, cropping, saving, etc.) interact within the pipeline.
    Concrete implementations provide the specific logic for each step.
    """

    @abc.abstractmethod
    def load(self, source_path: str) -> ImageData:
        """Loads image data from a specified source path.

        Implementations should handle reading various file formats and
        populating an ImageData object with the image data and
        initial relevant metadata (like dimensions, format, source path).

        Args:
            pass
            source_path: The path to the image file to load.

        Returns:
            An ImageData object containing the loaded image and initial metadata.

        Raises:
            FileNotFoundError: If the source_path does not exist.
            IOError: If there's an error reading the file.
            ValueError: If the file format is unsupported or invalid.
        """

    @abc.abstractmethod
    def process(self, image_data: ImageData, **kwargs: Any) -> ImageData:
        """Performs a specific processing step on the image data.

        This is a generic method intended for steps like filtering,
        color correction, reprojection (e.g., Sanchez), etc.
        Implementations should modify the image_data attribute of the
        input ImageData object or create a new one, potentially updating
        metadata to reflect the changes (e.g., adding processing steps)
        to a history log within metadata).

        Args:
            pass
            image_data: The ImageData object to process.
            **kwargs: Flexible keyword arguments specific to the processing
            step (e.g., reprojection parameters, filter settings).

        Returns:
            pass
            An ImageData object with the processed image and updated metadata.
        """

    @abc.abstractmethod
    def crop(self, image_data: ImageData, crop_area: tuple[int, int, int, int]) -> ImageData:
        """Crops the image data to the specified rectangular area.

        Implementations should extract the specified portion of the
        image_data attribute. The crop_area format should be clearly
        defined by implementations (e.g., (left, top, right, bottom))
        pixel coordinates). Metadata should be updated accordingly (e.g.,
        new dimensions).

        Args:
            pass
            image_data: The ImageData object to crop.
            crop_area: A tuple representing the area to crop. The exact
            meaning (e.g., pixel coordinates, percentages)
            should be defined by the implementation. A common
            convention is (left, top, right, bottom).

        Returns:
            An ImageData object containing the cropped image and updated
            metadata.

        Raises:
            ValueError: If the crop_area is invalid for the image dimensions.
        """

    @abc.abstractmethod
    def save(self, image_data: ImageData, destination_path: str) -> None:
        """Saves the image data to a specified destination path.

        Implementations should handle writing the image_data attribute
        to a file in a suitable format. The format might be determined
        by the file extension or specific arguments.

        Args:
            pass
            image_data: The ImageData object containing the data to save.
            destination_path: The file path where the image should be saved.

        Raises:
            IOError: If there's an error writing the file.
            ValueError: If the destination format is unsupported.
        """
