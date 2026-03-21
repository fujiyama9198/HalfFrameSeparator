from PIL import Image
import numpy as np
from scipy import ndimage as ndi
from pathlib import Path
import argparse
import itertools
import multiprocessing

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


def get_separation_center(mask1_blackband, *, verbose=False, left_right=False):
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
        if not left_right:
            center_idx = left + (starts[i] + ends[i] - 1) // 2
            if verbose:
                print(f"Center of longest True region: {center_idx}")
            return center_idx
        else:
            return left + starts[i], left + ends[i]


def separate_image(src_image, threshold, dilation, erosion, crop=None):
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
    if crop is None:
        center_idx = get_separation_center(detect_black_band(mask1_dilated, ignore_edges=erosion), left_right=False)
        dst1_image = src_image.crop((0, 0, center_idx, src_image.height))
        dst2_image = src_image.crop((center_idx, 0, src_image.width, src_image.height))
    else:
        left, right = get_separation_center(detect_black_band(mask1_dilated, ignore_edges=erosion), left_right=True)
        dst1_image = src_image.crop((0, 0, left - crop, src_image.height))
        dst2_image = src_image.crop((right + crop, 0, src_image.width, src_image.height))
    return dst1_image, dst2_image


class _HalfFrameFunctor:
    def __init__(self, threshold, dilation, erosion, crop, path_dstimgs, no_keep_exif):
        self.threshold = threshold
        self.dilation = dilation
        self.erosion = erosion
        self.crop = crop
        self.path_dstimgs = path_dstimgs
        self.no_keep_exif = no_keep_exif

    def __call__(self, path):
        src_image = Image.open(path)
        try:
            dst1_image, dst2_image = separate_image(src_image, self.threshold, self.dilation, self.erosion, crop=self.crop)
            dst1_path = self.path_dstimgs / f"{path.stem}_1{path.suffix}"
            dst2_path = self.path_dstimgs / f"{path.stem}_2{path.suffix}"
            if self.no_keep_exif:
                dst1_image.save(dst1_path)
                dst2_image.save(dst2_path)
            else:
                dst1_image.save(dst1_path, exif=src_image.info.get("exif"))
                dst2_image.save(dst2_path, exif=src_image.info.get("exif"))
        except Exception:
            dst_path = self.path_dstimgs / path.name
            if self.no_keep_exif:
                src_image.save(dst_path)
            else:
                src_image.save(dst_path, exif=src_image.info.get("exif"))
        return path


def main():
    parser = argparse.ArgumentParser(description="Half-frame image separator")
    parser.add_argument("indir", type=Path, help="Source image directory")
    parser.add_argument("--outdir", "-o", type=Path, help="Destination image directory")
    parser.add_argument("--threshold", "-t", type=int, default=64, help="Threshold for inter-frame margin")
    parser.add_argument("--dilation", "-d", type=int, default=7, help="Number of dilation iterations")
    parser.add_argument("--erosion", "-e", type=int, default=14, help="Number of erosion iterations")
    parser.add_argument("--crop", type=int, help="If specified, crop the detected inter-frame area by <value> so that no blank areas are included")
    parser.add_argument("--no-keep-exif", action="store_true", help="Do not keep EXIF data in output images")
    parser.add_argument("--num-processes", '-j', type=int, nargs='?', const=-1, default=None, help="Number of processes to use for parallel processing. If only the option without a number is specified, it uses all the available cores.")

    args = parser.parse_args()
    path_srcimgs = args.indir
    path_dstimgs = args.outdir if args.outdir else (path_srcimgs.with_name(f"{path_srcimgs.name}_separated"))
    path_dstimgs.mkdir(exist_ok=False, parents=True)

    if args.num_processes is not None and (args.num_processes < -1 or args.num_processes == 0):
        parser.error("--num-processes must be a positive integer or -1 to use all CPU cores.")

    file_ext = ["jpg", "JPG", "jpeg", "JPEG", "tif", "TIF", "tiff", "TIFF"]
    file_list = list(itertools.chain.from_iterable(path_srcimgs.glob("*." + ext) for ext in file_ext))

    _core = _HalfFrameFunctor(
        threshold=args.threshold,
        dilation=args.dilation,
        erosion=args.erosion,
        crop=args.crop,
        path_dstimgs=path_dstimgs,
        no_keep_exif=args.no_keep_exif
    )

    if args.num_processes is None:
        for path in tqdm(file_list):
            _core(path)
            tqdm.write(f"Processed {path.name}")
    else:
        num_processes = args.num_processes
        if num_processes == -1:
            num_processes = multiprocessing.cpu_count()
        with multiprocessing.Pool(num_processes) as pool:
            for _path in tqdm(pool.imap_unordered(_core, file_list), total=len(file_list)):
                tqdm.write(f"Processed {_path.name}")

if __name__ == "__main__":
    main()
