import os
import shutil
import cv2
import numpy as np
from PIL import Image


def image_blending(image_path, blend_image_path, blending_mode, alpha, output_dir):
    """
    Blends two images using advanced blend modes.
    Acts as a Clipping Mask: The final image strictly retains the input image's transparency.
    """
    # 1. Automatic Folder Creation & Output Path Generation
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext = os.path.splitext(base_name)[0]
    final_output_path = os.path.join(output_dir, f"{name_without_ext}.png")

    # 2. Read images with IMREAD_UNCHANGED to capture alpha channels
    base_img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    blend_img = cv2.imread(blend_image_path, cv2.IMREAD_UNCHANGED)
    
    if base_img is None or blend_img is None:
        raise ValueError(f"One or both image paths are invalid.\nBase Image: {image_path}\nBlend Image: {blend_image_path}")

    # 3. Bulletproof Channel Normalizer: Forces everything to 4-channel BGRA
    def enforce_bgra(img):
        if len(img.shape) == 2:  
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        elif len(img.shape) == 3:
            if img.shape[2] == 3:  
                return cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
            elif img.shape[2] == 4: 
                return img
            elif img.shape[2] == 2: 
                bgra = np.zeros((img.shape[0], img.shape[1], 4), dtype=np.uint8)
                bgra[:, :, :3] = cv2.cvtColor(img[:, :, 0], cv2.COLOR_GRAY2BGR) 
                bgra[:, :, 3] = img[:, :, 1] 
                return bgra
        return img
        
    base_img = enforce_bgra(base_img)
    blend_img = enforce_bgra(blend_img)

    # 4. Resize blend image to match base image dimensions exactly
    blend_img = cv2.resize(blend_img, (base_img.shape[1], base_img.shape[0]))
    
    # 5. Split Color (RGB) and Alpha (A), converting to high-precision float (0.0 to 1.0)
    A_rgb = base_img[:, :, :3].astype(np.float32) / 255.0
    A_alpha = base_img[:, :, 3:4].astype(np.float32) / 255.0
    
    B_rgb = blend_img[:, :, :3].astype(np.float32) / 255.0
    B_alpha = blend_img[:, :, 3:4].astype(np.float32) / 255.0
    
    eps = 1e-7
    mode = str(blending_mode).lower().strip()
    
    # 6. Apply Blending Mode Algorithms ONLY to the RGB channels
    if mode == 'multiply':
        blended_rgb = A_rgb * B_rgb
    elif mode == 'soft_light':
        blended_rgb = np.where(
            B_rgb < 0.5,
            A_rgb - (1.0 - 2.0 * B_rgb) * A_rgb * (1.0 - A_rgb),
            A_rgb + (2.0 * B_rgb - 1.0) * (np.sqrt(np.clip(A_rgb, 0, 1)) - A_rgb)
        )
    elif mode == 'hard_light':
        blended_rgb = np.where(
            B_rgb < 0.5,
            2.0 * A_rgb * B_rgb,
            1.0 - 2.0 * (1.0 - A_rgb) * (1.0 - B_rgb)
        )
    elif mode == 'overlay':
        blended_rgb = np.where(
            A_rgb < 0.5,
            2.0 * A_rgb * B_rgb,
            1.0 - 2.0 * (1.0 - A_rgb) * (1.0 - B_rgb)
        )
    elif mode == 'dodge':
        blended_rgb = A_rgb / np.maximum((1.0 - B_rgb), eps)
    elif mode == 'addition':
        blended_rgb = A_rgb + B_rgb
    elif mode == 'subtract':
        blended_rgb = A_rgb - B_rgb
    elif mode == 'darken_only':
        blended_rgb = np.minimum(A_rgb, B_rgb)
    elif mode == 'lighten_only':
        blended_rgb = np.maximum(A_rgb, B_rgb)
    elif mode == 'difference':
        blended_rgb = np.abs(A_rgb - B_rgb)
    elif mode == 'divide':
        blended_rgb = A_rgb / np.maximum(B_rgb, eps)
    elif mode == 'grain_extract':
        blended_rgb = A_rgb - B_rgb + 0.5
    elif mode == 'grain_merge':
        blended_rgb = A_rgb + B_rgb - 0.5
    elif mode == 'normal':
        blended_rgb = B_rgb
    else:
        raise ValueError(f"Unsupported blending mode: {blending_mode}")

    # Clip RGB bounds to keep data strictly between 0.0 and 1.0
    blended_rgb = np.clip(blended_rgb, 0.0, 1.0)
    
    # 7. Alpha parsing and Clipping Mask Compositing
    try:
        alpha_val = float(alpha)
    except (ValueError, TypeError):
        alpha_val = 1.0
        
    effective_alpha = B_alpha * alpha_val
    
    # Mix the colors: Where blend image is opaque, show blended math. Otherwise, show original color.
    final_rgb = (blended_rgb * effective_alpha) + (A_rgb * (1.0 - effective_alpha))
    
    # Force the final transparency to be EXACTLY the same as the input image
    final_alpha = A_alpha
    
    # 8. Recombine and enforce valid color values
    final_rgb = np.clip(final_rgb, 0.0, 1.0)
    final_bgra = np.concatenate([final_rgb, final_alpha], axis=2)
    
    # 9. Convert back to 8-bit image and save
    final_img = (final_bgra * 255.0).astype(np.uint8)
    cv2.imwrite(final_output_path, final_img)
    
    print(f"Blending complete. Saved to: {final_output_path}")
    return final_output_path

def image_masking(image_path, mask_image_path, output_dir):
    """
    Applies a mask to an image.
    - If Mask is Solid: Black removes the input, White keeps the input.
    - If Mask is Transparent: The visible shapes act as an ERASER, punching a hole in the input.
    """
    # 1. Automatic Folder Creation & Output Path Generation
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext = os.path.splitext(base_name)[0]
    final_output_path = os.path.join(output_dir, f"{name_without_ext}.png")

    # 2. Read images with IMREAD_UNCHANGED to capture alpha channels
    base_img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    mask_img = cv2.imread(mask_image_path, cv2.IMREAD_UNCHANGED)
    
    if base_img is None or mask_img is None:
        raise ValueError(f"One or both image paths are invalid.\nInput Image: {image_path}\nMask Image: {mask_image_path}")

    # 3. Universal normalizer for the Input Image (force to 4-channel BGRA)
    def enforce_bgra(img):
        if len(img.shape) == 2:  # Grayscale
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        elif len(img.shape) == 3:
            if img.shape[2] == 3:  # Solid RGB/BGR
                return cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
            elif img.shape[2] == 4: # Already RGBA
                return img
            elif img.shape[2] == 2: # Gray + Alpha
                bgra = np.zeros((img.shape[0], img.shape[1], 4), dtype=np.uint8)
                bgra[:, :, :3] = cv2.cvtColor(img[:, :, 0], cv2.COLOR_GRAY2BGR) 
                bgra[:, :, 3] = img[:, :, 1] 
                return bgra
        return img
        
    base_img = enforce_bgra(base_img)

    # 4. Intelligent Mask Extraction
    extracted_mask = None
    
    if len(mask_img.shape) == 3 and mask_img.shape[2] == 4:
        # Check if it actually HAS transparency
        if np.min(mask_img[:, :, 3]) < 255:
            # ERASER LOGIC: Invert the mask's alpha channel.
            extracted_mask = 255 - mask_img[:, :, 3]
        else:
            # Grayscale color masking fallback
            extracted_mask = cv2.cvtColor(mask_img[:, :, :3], cv2.COLOR_BGR2GRAY)
            
    elif len(mask_img.shape) == 3 and mask_img.shape[2] == 3:
        extracted_mask = cv2.cvtColor(mask_img, cv2.COLOR_BGR2GRAY)
        
    elif len(mask_img.shape) == 2:
        extracted_mask = mask_img
        
    else:
        raise ValueError("Unsupported mask image format.")

    # 5. Resize extracted mask to match base image dimensions exactly
    extracted_mask = cv2.resize(extracted_mask, (base_img.shape[1], base_img.shape[0]))
    
    # 6. Combine Transparency (Input Alpha * Mask Opacity)
    base_alpha = base_img[:, :, 3].astype(np.float32) / 255.0
    mask_opacity = extracted_mask.astype(np.float32) / 255.0
    
    final_alpha = base_alpha * mask_opacity
    
    # 7. Apply the new Alpha channel to the base image
    base_img[:, :, 3] = (final_alpha * 255.0).astype(np.uint8)
    
    # 8. Save the final image
    cv2.imwrite(final_output_path, base_img)
    
    print(f"Masking complete. Saved to: {final_output_path}")
    return final_output_path

def image_resize(image_path, width, height, output_dir):
    """
    Resizes an image dynamically.
    - If only width is given, height auto-scales.
    - If only height is given, width auto-scales.
    - If both are given, it forces those exact dimensions.
    - Preserves format (JPG stays JPG) UNLESS the image has transparency, in which case it forces PNG.
    """
    os.makedirs(output_dir, exist_ok=True)
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    
    if img is None:
        raise ValueError(f"Could not read image at {image_path}")
        
    orig_h, orig_w = img.shape[:2]
    
    # Clean parameter types
    def clean_dim(val):
        if val is None or str(val).lower() == 'none' or str(val).strip() == '':
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    w_val = clean_dim(width)
    h_val = clean_dim(height)

    # Calculate new dimensions
    if w_val is not None and h_val is None:
        ratio = float(w_val) / orig_w
        new_w = w_val
        new_h = int(orig_h * ratio)
    elif h_val is not None and w_val is None:
        ratio = float(h_val) / orig_h
        new_h = h_val
        new_w = int(orig_w * ratio)
    elif w_val is not None and h_val is not None:
        new_w = w_val
        new_h = h_val
    else:
        new_w = orig_w
        new_h = orig_h

    # Choose interpolation method
    if new_w < orig_w or new_h < orig_h:
        interpolation_method = cv2.INTER_AREA
    else:
        interpolation_method = cv2.INTER_CUBIC
        
    resized_img = cv2.resize(img, (new_w, new_h), interpolation=interpolation_method)
    
    # Path generation
    base_name = os.path.basename(image_path)
    name_without_ext, original_ext = os.path.splitext(base_name)
    
    has_alpha = (len(resized_img.shape) == 3 and resized_img.shape[2] == 4)
    final_ext = ".png" if has_alpha else (original_ext if original_ext else ".jpg")
        
    final_output_path = os.path.join(output_dir, f"{name_without_ext}{final_ext}")
    cv2.imwrite(final_output_path, resized_img)
    print(f"Resized to {new_w}x{new_h}. Saved to: {final_output_path}")
    
    return final_output_path

def image_canvas_change(image_path, new_width, new_height, orientation, output_dir):
    """
    Changes the canvas size by cropping or adding transparent space.
    Strictly follows exact anchor orientations.
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext = os.path.splitext(base_name)[0]
    final_output_path = os.path.join(output_dir, f"{name_without_ext}.png")

    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Could not read image at {image_path}")
        
    def enforce_bgra(img):
        if len(img.shape) == 2:  
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        elif len(img.shape) == 3:
            if img.shape[2] == 3:  
                return cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
            elif img.shape[2] == 4: 
                return img
        return img
        
    img = enforce_bgra(img)
    orig_h, orig_w = img.shape[:2]
    
    def clean_dim(val, fallback):
        if val is None or str(val).lower() == 'none' or str(val).strip() == '':
            return fallback
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return fallback

    target_w = clean_dim(new_width, orig_w)
    target_h = clean_dim(new_height, orig_h)

    # Transparent canvas
    canvas = np.zeros((target_h, target_w, 4), dtype=np.uint8)
    
    ori = str(orientation).lower().strip()
    if ori == 'center':
        offset_x = (target_w - orig_w) // 2
        offset_y = (target_h - orig_h) // 2
    elif ori == 'left':
        offset_x = 0
        offset_y = (target_h - orig_h) // 2
    elif ori == 'right':
        offset_x = target_w - orig_w
        offset_y = (target_h - orig_h) // 2
    elif ori == 'top':
        offset_x = (target_w - orig_w) // 2
        offset_y = 0
    elif ori == 'bottom':
        offset_x = (target_w - orig_w) // 2
        offset_y = target_h - orig_h
    elif ori in ['left-top', 'top-left']:
        offset_x = 0
        offset_y = 0
    elif ori in ['top-right', 'right-top']:
        offset_x = target_w - orig_w
        offset_y = 0
    elif ori in ['right-bottom', 'bottom-right']:
        offset_x = target_w - orig_w
        offset_y = target_h - orig_h
    elif ori in ['bottom-left', 'left-bottom']:
        offset_x = 0
        offset_y = target_h - orig_h
    else:
        raise ValueError(f"Unknown orientation: {orientation}")

    dest_x_start = max(0, offset_x)
    dest_y_start = max(0, offset_y)
    dest_x_end = min(target_w, offset_x + orig_w)
    dest_y_end = min(target_h, offset_y + orig_h)
    
    src_x_start = dest_x_start - offset_x
    src_y_start = dest_y_start - offset_y
    src_x_end = dest_x_end - offset_x
    src_y_end = dest_y_end - offset_y

    if (dest_x_end > dest_x_start) and (dest_y_end > dest_y_start):
        canvas[dest_y_start:dest_y_end, dest_x_start:dest_x_end] = img[src_y_start:src_y_end, src_x_start:src_x_end]

    cv2.imwrite(final_output_path, canvas)
    print(f"Canvas changed to {target_w}x{target_h} using '{ori}' anchor. Saved to: {final_output_path}")
    return final_output_path

def rename_file_or_directory(source_path, new_name):
    """
    Renames a file or directory.
    Automatically preserves the original file extension if missing in new_name.
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Error: The path '{source_path}' does not exist.")
        
    parent_directory = os.path.dirname(source_path)
    
    if os.path.isfile(source_path):
        _, original_ext = os.path.splitext(source_path)
        _, new_ext = os.path.splitext(new_name)
        if not new_ext and original_ext:
            new_name = new_name + original_ext
    
    new_path = os.path.join(parent_directory, new_name)
    
    if os.path.exists(new_path) and new_path != source_path:
        raise FileExistsError(f"Error: '{new_name}' already exists in that location.")
        
    os.rename(source_path, new_path)
    print(f"Successfully renamed to: {new_path}")
    return new_path

def image_converter(image_path, target_extension, output_dir):
    """
    Converts any raster image to a specified format.
    Supported outputs: .jpg, .jpeg, .png, .webp, .avif, .gif, .bmp, .jxl, .heic, .heif
    """
    os.makedirs(output_dir, exist_ok=True)

    # Dynamic Plugin Registration
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass

    try:
        import pillow_avif
    except ImportError:
        pass

    try:
        import pillow_jxl
    except ImportError:
        pass

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Error: Could not find '{image_path}'")

    target_ext = str(target_extension).lower().strip()
    if not target_ext.startswith('.'):
        target_ext = f".{target_ext}"
        
    base_name = os.path.basename(image_path)
    name_without_ext = os.path.splitext(base_name)[0]
    final_output_path = os.path.join(output_dir, f"{name_without_ext}{target_ext}")
    
    if image_path == final_output_path:
        final_output_path = os.path.join(output_dir, f"{name_without_ext}_converted{target_ext}")

    img = Image.open(image_path)
    formats_without_alpha = ['.jpg', '.jpeg', '.bmp', '.heic', '.heif']
    
    if target_ext in formats_without_alpha and img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[3]) 
        img = background
    elif img.mode == 'P':
        img = img.convert('RGBA' if 'transparency' in img.info else 'RGB')

    img.save(final_output_path)
    print(f"Successfully converted to {target_ext}: {final_output_path}")
    return final_output_path

def copy_file_or_directory(source_path, destination_dir, new_name="", preserve_tree=False, root_dir=""):
    """
    Copies a file or directory and forcibly overwrites if existing.
    If preserve_tree is True, it replicates the folder hierarchy from root_dir.
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Error: The source path '{source_path}' does not exist.")
        
    # Preserve Tree Structure Logic
    is_preserve = bool(preserve_tree) if not isinstance(preserve_tree, str) else (preserve_tree.lower() == 'true')
    if is_preserve and root_dir and source_path.startswith(root_dir):
        target_item_dir = os.path.dirname(source_path) if os.path.isfile(source_path) else source_path
        rel_path = os.path.relpath(target_item_dir, root_dir)
        if rel_path != "." and rel_path != "":
            destination_dir = os.path.join(destination_dir, rel_path)
            
    os.makedirs(destination_dir, exist_ok=True)
    
    original_name = os.path.basename(source_path)
    final_name = new_name if new_name else original_name
    
    if os.path.isfile(source_path) and new_name:
        _, original_ext = os.path.splitext(source_path)
        _, new_ext = os.path.splitext(final_name)
        if not new_ext and original_ext:
            final_name = final_name + original_ext
            
    destination_path = os.path.join(destination_dir, final_name)
    
    if os.path.exists(destination_path):
        if os.path.isfile(destination_path) or os.path.islink(destination_path):
            os.remove(destination_path)
        elif os.path.isdir(destination_path):
            shutil.rmtree(destination_path)
            
    if os.path.isfile(source_path):
        shutil.copy2(source_path, destination_path)
    elif os.path.isdir(source_path):
        shutil.copytree(source_path, destination_path)
        
    print(f"Successfully force-copied to: {destination_path}")
    return destination_path

def move_file_or_directory(source_path, destination_dir, new_name="", preserve_tree=False, root_dir=""):
    """
    Moves a file or directory and forcibly overwrites if existing.
    If preserve_tree is True, it replicates the folder hierarchy from root_dir.
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Error: The source path '{source_path}' does not exist.")
        
    # Preserve Tree Structure Logic
    is_preserve = bool(preserve_tree) if not isinstance(preserve_tree, str) else (preserve_tree.lower() == 'true')
    if is_preserve and root_dir and source_path.startswith(root_dir):
        target_item_dir = os.path.dirname(source_path) if os.path.isfile(source_path) else source_path
        rel_path = os.path.relpath(target_item_dir, root_dir)
        if rel_path != "." and rel_path != "":
            destination_dir = os.path.join(destination_dir, rel_path)
            
    os.makedirs(destination_dir, exist_ok=True)
    
    original_name = os.path.basename(source_path)
    final_name = new_name if new_name else original_name
    
    if os.path.isfile(source_path) and new_name:
        _, original_ext = os.path.splitext(source_path)
        _, new_ext = os.path.splitext(final_name)
        if not new_ext and original_ext:
            final_name = final_name + original_ext
            
    destination_path = os.path.join(destination_dir, final_name)
    
    if os.path.exists(destination_path):
        if os.path.isfile(destination_path) or os.path.islink(destination_path):
            os.remove(destination_path)
        elif os.path.isdir(destination_path):
            shutil.rmtree(destination_path)
            
    shutil.move(source_path, destination_path)
    print(f"Successfully moved to: {destination_path}")
    return destination_path

def remove_background(image_path, output_dir, generate_mask=False):
    """
    Removes the background from an image using AI (rembg).
    Runs as an isolated Subprocess to prevent GUI crashes.
    Optional: Generates a B&W mask alongside the output if generate_mask is True.
    """
    import os
    import sys
    import subprocess

    os.makedirs(output_dir, exist_ok=True)
    
    base_name = os.path.basename(image_path)
    name_without_ext = os.path.splitext(base_name)[0]
    final_output_path = os.path.join(output_dir, f"{name_without_ext}.png")
    mask_output_path = os.path.join(output_dir, f"{name_without_ext}_mask.png")

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Error: Could not find image at '{image_path}'")

    print(f"🤖 AI processing background removal for: {base_name}...")

    # String parsing for UI checkbox compatibility
    is_mask_req = str(generate_mask).lower() == 'true'

    # ==========================================
    # 🚀 ISOLATED AI PROCESS SCRIPT
    # ==========================================
    script_code = f'''
import sys
try:
    from rembg import remove, new_session
    from PIL import Image
    import onnxruntime as ort
    

    available_providers = ort.get_available_providers()
    providers = []
    
    if 'CUDAExecutionProvider' in available_providers:
        providers.append('CUDAExecutionProvider')
    if 'DmlExecutionProvider' in available_providers:
        providers.append('DmlExecutionProvider')
    providers.append('CPUExecutionProvider')
    
    session = new_session("u2net", providers=providers)
    
    input_image = Image.open(r"""{image_path}""")
    output_image = remove(input_image, session=session)
    
    # Save transparent PNG
    output_image.save(r"""{final_output_path}""", format="PNG")
    
    # Save mask if requested by user
    if {is_mask_req}:
        if output_image.mode == 'RGBA':
            r, g, b, a = output_image.split()
            a.save(r"""{mask_output_path}""", format="PNG")
            
except Exception as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)
'''

    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        result = subprocess.run(
            [sys.executable, "-c", script_code],
            capture_output=True,
            text=True,
            startupinfo=startupinfo
        )
        
        if result.returncode != 0:
            print(f"❌ AI Engine Error: {result.stderr.strip()}")
            raise RuntimeError(f"rembg processing failed: {result.stderr.strip()}")
            
        print(f"✅ Background removed successfully. Saved to: {final_output_path}")
        if is_mask_req:
            print(f"✅ Mask generated successfully. Saved to: {mask_output_path}")
            
        return final_output_path
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR in process: {str(e)}")
        raise e
    
def extract_alpha_mask(image_path, output_dir):
    """
    Extracts the Alpha channel to create a perfect B&W mask.
    Foreground = White, Background = Black (Transparent areas).
    Handles soft edges perfectly.
    """

    # 1. Output folder setup
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext = os.path.splitext(base_name)[0]
    final_output_path = os.path.join(output_dir, f"{name_without_ext}_mask.png")

    # 2. Image ko IMREAD_UNCHANGED ke sath load karein taaki Alpha channel read ho
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Could not read image at {image_path}")

    # 3. Check karein ki image mein 4 channels (RGBA) hain ya nahi
    if len(img.shape) == 3 and img.shape[2] == 4:
        # Alpha channel ko alag nikal lein
        alpha_channel = img[:, :, 3]
        cv2.imwrite(final_output_path, alpha_channel)
        print(f"✅ Mask extracted perfectly. Saved to: {final_output_path}")
    else:
        # Agar image solid hai (koi transparency nahi), toh poori image ko white mask bana dein
        print(f"⚠️ No transparency found. Generating solid white mask.")
        mask = np.ones(img.shape[:2], dtype=np.uint8) * 255
        cv2.imwrite(final_output_path, mask)
        
    return final_output_path

def create_thumbnail(image_path, width, height, gap, output_dir):
    """
    Creates a smart thumbnail with proportional scaling and padding (gap).
    - Transparent Images: Auto-trims empty space first, keeps transparent background.
    - Solid Images: Fits proportionally and adds a white background.
    """
    import os
    import cv2
    import numpy as np

    # 1. Output directory setup
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext = os.path.splitext(base_name)[0]

    # 2. Image Read karein
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Could not read image at {image_path}")

    # 3. Parameters clean karein (Agar user khali chhod de toh default lega)
    def clean_int(val, default=0):
        if val is None or str(val).lower() == 'none' or str(val).strip() == '':
            return default
        try:
            return int(float(val))
        except:
            return default

    # Default sizes fallback
    w_val = clean_int(width, 500)
    h_val = clean_int(height, 500)
    gap_val = clean_int(gap, 0)

    # 4. Usable area (Charo taraf se gap minus karna)
    usable_w = w_val - (2 * gap_val)
    usable_h = h_val - (2 * gap_val)

    if usable_w <= 0 or usable_h <= 0:
        raise ValueError(f"Gap ({gap_val}px) is too large for the given Width({w_val}) or Height({h_val}).")

    has_alpha = (len(img.shape) == 3 and img.shape[2] == 4)

    # 5. AUTO-TRIM (Agar transparency hai, toh khali area kaat do)
    if has_alpha:
        alpha = img[:, :, 3]
        coords = cv2.findNonZero(alpha)
        if coords is not None:
            x, y, w_rect, h_rect = cv2.boundingRect(coords)
            img = img[y:y+h_rect, x:x+w_rect]

    # 6. Proportional Resize Logic (Aspect Ratio Lock)
    orig_h, orig_w = img.shape[:2]
    scale = min(usable_w / orig_w, usable_h / orig_h)
    new_w = max(1, int(orig_w * scale))
    new_h = max(1, int(orig_h * scale))

    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    resized_img = cv2.resize(img, (new_w, new_h), interpolation=interpolation)

    # 7. Final Canvas Create Karein
    if has_alpha:
        # Transparent Background
        canvas = np.zeros((h_val, w_val, 4), dtype=np.uint8)
        final_ext = ".png"
    else:
        # White Background
        if len(img.shape) == 2:  # Grayscale to Color
            resized_img = cv2.cvtColor(resized_img, cv2.COLOR_GRAY2BGR)
        elif resized_img.shape[2] == 4: # Drop alpha if somehow present
            resized_img = cv2.cvtColor(resized_img, cv2.COLOR_BGRA2BGR)
            
        canvas = np.ones((h_val, w_val, 3), dtype=np.uint8) * 255  # Solid White
        final_ext = ".jpg"

    # 8. Center Positioning (Image ko canvas ke theek beech mein paste karein)
    x_offset = (w_val - new_w) // 2
    y_offset = (h_val - new_h) // 2
    canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized_img

    # 9. Save karein
    final_output_path = os.path.join(output_dir, f"{name_without_ext}_thumb{final_ext}")
    cv2.imwrite(final_output_path, canvas)
    
    print(f"✅ Thumbnail created ({w_val}x{h_val} with {gap_val}px gap). Saved to: {final_output_path}")
    return final_output_path

def delete_file_or_folder(target_path, target_names, match_type="contains"):
    """
    Deletes a file or directory if its name matches the given criteria.
    - target_names: Can be a single string or a comma-separated list (e.g., "temp, backup, .ini").
    - match_type: 'contains' (default) or 'exact'.
    """
    import os
    import shutil

    # 1. Path exist check
    if not target_path or not os.path.exists(target_path):
        return target_path

    base_name = os.path.basename(target_path)
    
    # 2. Parse target_names into a list (Handles both string and list inputs)
    if isinstance(target_names, str):
        # Split by comma and clean up spaces for UI compatibility
        name_list = [n.strip().lower() for n in target_names.split(",") if n.strip()]
    elif isinstance(target_names, list):
        name_list = [str(n).strip().lower() for n in target_names if str(n).strip()]
    else:
        name_list = [str(target_names).strip().lower()]

    if not name_list:
        return target_path  # Nothing to match

    match_mode = str(match_type).lower().strip()
    target_lower = base_name.lower()
    
    should_delete = False
    
    # 3. Matching Logic
    for name in name_list:
        if match_mode == "exact":
            if target_lower == name:
                should_delete = True
                break
        else:  # Default to 'contains'
            if name in target_lower:
                should_delete = True
                break

    # 4. Deletion Logic
    if should_delete:
        try:
            if os.path.isfile(target_path) or os.path.islink(target_path):
                os.remove(target_path)
                print(f"🗑️ [DELETED FILE]: {target_path}")
            elif os.path.isdir(target_path):
                shutil.rmtree(target_path)
                print(f"🗑️ [DELETED DIRECTORY]: {target_path}")
        except Exception as e:
            print(f"❌ [DELETE FAILED] Could not delete {target_path}. Error: {str(e)}")
            raise e

    return target_path

def run_custom_user_code(code_text, **context_vars):
    """
    Executes raw Python code typed by the user in the UI.
    Receives ALL local variables (loops, paths, function returns) automatically.
    """
    import os
    import sys
    import cv2
    import shutil
    import numpy as np

    if not code_text or str(code_text).strip() == "" or str(code_text) == "None":
        print("⚠️ No custom code to run. Skipping.")
        return None

    print("⚡ Executing Custom User Code...")
    
    # User ke code ko basic libraries automatically mil jayengi
    context_vars.update({
        'os': os, 'sys': sys, 'cv2': cv2, 'np': np, 'shutil': shutil
    })
    
    try:
        # User ka code saare variables ke sath run hoga
        exec(code_text, globals(), context_vars)
        print("✅ Custom code executed successfully.")
    except Exception as e:
        print(f"❌ Error in custom code: {str(e)}")
        raise e
        
    # Agar user ne apne code mein 'result = ...' likha hai, toh usko return kar do
    return context_vars.get('result', None)

def search_and_copy(source_path, dest_dir, search_input, mode="contains", ignore_case=True):
    """
    Evaluates a single FILE or DIRECTORY against the search criteria and copies it if matched.
    Designed to be seamlessly mapped inside your external master loop.
    
    :param source_path: The full path of the single file or folder to check.
    :param dest_dir: Folder where the item will be copied if it matches.
    :param search_input: Can be a list, a single string, or a '.txt' file path.
    :param mode: 'exact', 'contains', or 'extension'.
    :param ignore_case: Case-insensitive matching if True.
    :return: The destination path if copied, or None if no match/failure.
    """
    if not os.path.exists(source_path):
        return None 

    queries = []
    if isinstance(search_input, str):
        if search_input.lower().endswith('.txt') and os.path.exists(search_input):
            with open(search_input, 'r', encoding='utf-8') as f:
                queries = [line.strip() for line in f if line.strip()]
        else:
            queries = [search_input.strip()]
    elif isinstance(search_input, list):
        queries = [str(q).strip() for q in search_input if str(q).strip()]
    else:
        return None

    if not queries:
        return None

    is_dir = os.path.isdir(source_path)
    item_name = os.path.basename(source_path)
    
    if is_dir:
        item_base = item_name
        item_ext = ""  
    else:
        item_base, item_ext = os.path.splitext(item_name)
        
    match_found = False
    
    for query in queries:
        q_val = query.lower() if ignore_case else query
        i_val = item_name.lower() if ignore_case else item_name
        ib_val = item_base.lower() if ignore_case else item_base
        
        if mode == "exact":
            if '.' in query and not query.startswith('.'):
                if i_val == q_val:
                    match_found = True
                    break
            else:
                if ib_val == q_val:
                    match_found = True
                    break
                    
        elif mode == "contains":
            if q_val in i_val:
                match_found = True
                break
                
        elif mode == "extension":
            if not is_dir: 
                ext = q_val if q_val.startswith('.') else f".{q_val}"
                if i_val.endswith(ext):
                    match_found = True
                    break

    if match_found:
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, item_name)
        
        copied_count = 1
        while os.path.exists(dest_path):
            if is_dir:
                dest_path = os.path.join(dest_dir, f"{item_base}_{copied_count}")
            else:
                dest_path = os.path.join(dest_dir, f"{item_base}_{copied_count}{item_ext}")
            copied_count += 1
        
        try:
            if is_dir:
                shutil.copytree(source_path, dest_path)
            else:
                shutil.copy2(source_path, dest_path)
                
            print(f"✅ Matched & Copied: {item_name} -> {dest_path}")
            return dest_path
        except Exception as e:
            print(f"❌ Failed to copy {item_name}: {e}")
            return None
            
    return None

def image_blur(image_path, blur_value, output_dir):
    """
    Applies a Gaussian blur to an image based on the provided blur_value.
    - Automatically ensures the blur kernel size is an odd number (required by OpenCV).
    - Preserves alpha channels (transparency) for RGBA images.
    """
    # 1. Automatic Folder Creation & Output Path Generation
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext, original_ext = os.path.splitext(base_name)
    
    # Format preservation logic (Transparent images force PNG, others keep original)
    img_test = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img_test is None:
        raise ValueError(f"Could not read image at {image_path}")
    
    has_alpha = (len(img_test.shape) == 3 and img_test.shape[2] == 4)
    final_ext = ".png" if has_alpha else (original_ext if original_ext else ".jpg")
    final_output_path = os.path.join(output_dir, f"{name_without_ext}_blurred{final_ext}")

    # 2. Read image with IMREAD_UNCHANGED to capture alpha channels
    base_img = img_test
    
    # 3. Universal Channel Normalizer (Forces BGRA or BGR format safely)
    def enforce_channels(img):
        if len(img.shape) == 2:  # Grayscale
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA) if has_alpha else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif len(img.shape) == 3:
            if img.shape[2] == 3 and has_alpha:
                return cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
            elif img.shape[2] == 4 and not has_alpha:
                return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img
        
    base_img = enforce_channels(base_img)

    # 4. Clean and parse blur parameter
    try:
        kernel_size = int(float(blur_value))
    except (ValueError, TypeError):
        kernel_size = 0

    # 5. Apply Gaussian Blur Logic
    if kernel_size <= 0:
        print(f"⚠️ Blur value is 0 or invalid. Saving original image: {base_name}")
        blurred_img = base_img
    else:
        # OpenCV GaussianBlur requires kernel size to be a positive ODD integer
        if kernel_size % 2 == 0:
            kernel_size += 1  # Convert even number to the next odd number
            
        blurred_img = cv2.GaussianBlur(base_img, (kernel_size, kernel_size), 0)

    # 6. Save the final blurred image
    cv2.imwrite(final_output_path, blurred_img)
    print(f"✅ Blur complete (Kernel: {kernel_size}x{kernel_size}). Saved to: {final_output_path}")
    
    return final_output_path

def image_sharpen(image_path, strength, output_dir):
    """
    Sharpens an image using a customizable convolution kernel.
    - strength: Controls the intensity of the sharpening effect (e.g., 1.0 to 5.0).
    - Preserves alpha channels (transparency) for RGBA images.
    """
    # 1. Automatic Folder Creation & Output Path Generation
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext, original_ext = os.path.splitext(base_name)
    
    # 2. Read image with IMREAD_UNCHANGED to detect alpha channel
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Could not read image at {image_path}")
        
    has_alpha = (len(img.shape) == 3 and img.shape[2] == 4)
    final_ext = ".png" if has_alpha else (original_ext if original_ext else ".jpg")
    final_output_path = os.path.join(output_dir, f"{name_without_ext}_sharpened{final_ext}")

    # 3. Clean and parse strength parameter
    try:
        strength_val = float(strength)
    except (ValueError, TypeError):
        strength_val = 1.0  # Default fallback strength

    # 4. Handle Color Channels and Alpha Separation
    if has_alpha:
        bgr = img[:, :, :3]
        alpha = img[:, :, 3]
    else:
        bgr = img
        alpha = None

    # 5. Define Sharpening Kernel Matrix based on Strength
    # Center weight dynamic calculation based on strength
    center_weight = 4.0 + max(0.5, strength_val)
    kernel = np.array([[ 0, -1,  0],
                       [-1, center_weight, -1],
                       [ 0, -1,  0]], dtype=np.float32)

    # 6. Apply Filter to Image
    sharpened_bgr = cv2.filter2D(bgr, -1, kernel)

    # 7. Recombine Alpha channel if it originally existed
    if has_alpha:
        sharpened_img = cv2.merge([
            sharpened_bgr[:, :, 0], 
            sharpened_bgr[:, :, 1], 
            sharpened_bgr[:, :, 2], 
            alpha
        ])
    else:
        sharpened_img = sharpened_bgr

    # 8. Save the final output image
    cv2.imwrite(final_output_path, sharpened_img)
    print(f"✅ Sharpening complete (Strength: {strength_val}). Saved to: {final_output_path}")
    
    return final_output_path

def manual_mask_inpaint_setup(image_path, mask_path, output_dir):
    """
    UI Node Editor se '🖌️ Draw' dabakar isme mask_path laayein.
    Ye function simply pipeline forward karne ke liye hai.
    """
    import shutil
    import os
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "passed_image.png")
    shutil.copy(image_path, out_path)
    return out_path


# search_and_copy_files("D:/PythonProjects/universalCodeGen", "D:/PythonProjects/universalCodeGen/dest", "Copy", mode="contains")
# delete_file_or_folder(target_path, target_names, match_type="contains")
# create_thumbnail("BgRemov/input1.png", 100, 100, 20, "BgRemov/thumbnails")
# remove_background("BgRemov/input (2)BgRemov0707BgRemov5218_akash_akash.jpg", "BgRemov")
# extract_alpha_mask("BgRemov/input.png", "BgRemov/input_mask.png")
