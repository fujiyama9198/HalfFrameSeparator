from PIL import Image
import numpy as np
from scipy import ndimage as ndi
from pathlib import Path
import argparse
import itertools

try:
    from tqdm.auto import tqdm
except:
    def tqdm(iterable):
        return iterable


def get_mask(image_arr, threshold=64):
    """Create a binary mask where pixels darker than threshold are True.
    
    Args:
        image_arr: Input image array (H, W, C)
        threshold: Darkness threshold value (default: 64)
    
    Returns:
        Boolean mask array where all channels are below threshold
    """
    return (image_arr < threshold).all(axis=2)


def smooth_mask(mask1, iterations_dilation=7, iterations_erosion=14):
    """Smooth mask using morphological dilation followed by erosion.
    
    Args:
        mask1: Input binary mask
        iterations_dilation: Number of dilation iterations (default: 7)
        iterations_erosion: Number of erosion iterations (default: 14)
    
    Returns:
        Smoothed binary mask
    """
    structure = np.ones((3, 3), dtype=bool)  # 3x3 structuring element

    mask1_dilated = ndi.binary_dilation(mask1, structure=structure, iterations=iterations_dilation)
    mask1_dilated = ndi.binary_erosion(mask1_dilated, structure=structure, iterations=iterations_erosion)
    return mask1_dilated


def detect_black_band(mask1_dilated, ignore_edges=14):
    """Detect continuous black band by checking which columns are entirely dark.
    
    Args:
        mask1_dilated: Dilated binary mask
        ignore_edges: Number of pixels to ignore from top/bottom (default: 14)
    
    Returns:
        Boolean array indicating which columns are dark across the central region
    """
    mask1_blackband = mask1_dilated[ignore_edges:-ignore_edges, :].all(axis=0, keepdims=True)
    return mask1_blackband


def get_separation_center(mask1_blackband, *, verbose=False):
    """Find the center of the black band separation line in the image.
    
    Searches for the longest continuous True region in the central 40-60% 
    of the image width to locate the frame separation line.
    
    Args:
        mask1_blackband: Boolean array indicating dark columns
        verbose: Print debug information (default: False)
    
    Returns:
        Column index of the separation center
    
    Raises:
        ValueError: If no continuous dark region found in central area
    """
    line = mask1_blackband[0]  # shape: (W,)
    W = line.size

    # Central ±10% => [40%, 60%) range
    left = int(W * 0.4)
    right = int(W * 0.6)

    sub = line[left:right].astype(np.int8)

    # Detect start and end positions of continuous True regions
    d = np.diff(np.r_[0, sub, 0])
    starts = np.where(d == 1)[0]
    ends = np.where(d == -1)[0]  # ends is the position after termination

    if len(starts) == 0:
        raise ValueError("No continuous True region found in the specified range.")
    else:
        lengths = ends - starts
        i = lengths.argmax()  # Longest continuous region
        # Center position on original mask1_blackband (float)
        center_idx = left + (starts[i] + ends[i] - 1) // 2
        if verbose:
            print(f"Center of longest True region: {center_idx}")
    return center_idx


def separate_image(src_image, threshold, dilation, erosion):
    """Separate a half-frame image into two individual frames.
    
    Args:
        src_image: Source PIL Image object
        threshold: Darkness threshold for black band detection
        dilation: Number of dilation iterations
        erosion: Number of erosion iterations
    
    Returns:
        Tuple of two separated PIL Image objects
    """
    src_arr = np.asarray(src_image)
    mask = get_mask(src_arr, threshold=threshold)
    mask1_dilated = smooth_mask(mask, iterations_dilation=dilation, iterations_erosion=erosion)
    center_idx = get_separation_center(detect_black_band(mask1_dilated, ignore_edges=erosion))
    dst1_image = src_image.crop((0, 0, center_idx, src_image.height))
    dst2_image = src_image.crop((center_idx, 0, src_image.width, src_image.height))
    return dst1_image, dst2_image


def main():
    parser = argparse.ArgumentParser(description="Half-frame image separator")
    parser.add_argument("indir", type=Path, help="Source image directory")
    parser.add_argument("--outdir", "-o", type=Path, help="Destination image directory")
    parser.add_argument("--threshold", "-t", type=int, default=64, help="Threshold for inter-frame margin")
    parser.add_argument("--dilation", "-d", type=int, default=7, help="Number of dilation iterations")
    parser.add_argument("--erosion", "-e", type=int, default=14, help="Number of erosion iterations")
    parser.add_argument("--no-keep-exif", action="store_true", help="Do not keep EXIF data in output images")

    args = parser.parse_args()
    path_srcimgs = args.indir
    path_dstimgs = args.outdir if args.outdir else (path_srcimgs.with_name(f"{path_srcimgs.name}_separated"))
    path_dstimgs.mkdir(exist_ok=False, parents=True)

    file_ext = ["jpg", "JPG", "jpeg", "JPEG", "tif", "TIF", "tiff", "TIFF"]
    file_list = list(itertools.chain.from_iterable(path_srcimgs.glob("*." + ext) for ext in file_ext))
    for path in tqdm(file_list):
        src_image = Image.open(path)
        try:
            dst1_image, dst2_image = separate_image(src_image, args.threshold, args.dilation, args.erosion)
            dst1_path = path_dstimgs / f"{path.stem}_1{path.suffix}"
            dst2_path = path_dstimgs / f"{path.stem}_2{path.suffix}"
            if args.no_keep_exif:
                dst1_image.save(dst1_path)
                dst2_image.save(dst2_path)
            else:
                dst1_image.save(dst1_path, exif=src_image.info.get("exif"))
                dst2_image.save(dst2_path, exif=src_image.info.get("exif"))
        except Exception:
            dst_path = path_dstimgs / path.name
            if args.no_keep_exif:
                src_image.save(dst_path)
            else:
                src_image.save(dst_path, exif=src_image.info.get("exif"))
        tqdm.write(f"Processed {path.name}")


if __name__ == "__main__":
    main()
