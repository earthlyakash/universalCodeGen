import os
import cv2
import numpy as np
import urllib.request
from PIL import Image
import onnxruntime 

# ----------- YAHAN SE NAYA CODE ADD KAREIN -----------
import torch
import torch.serialization

_orig_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    kwargs['weights_only'] = False
    return _orig_torch_load(*args, **kwargs)

torch.load = _patched_torch_load
torch.serialization.load = _patched_torch_load
# -----------------------------------------------------



def levindabhi_cloth_segmentation(image_path, output_dir, 
                                  extract_upper_cloth=True, 
                                  extract_lower_cloth=False, 
                                  extract_full_dress=False,
                                  mask_offset=0, 
                                  mask_blur=0, 
                                  save_mask_only=False):
    """
    Model Name: u2net_cloth_seg.onnx
    Original Repo: levindabhi/cloth-segmentation
    Extracts clothing into SEPARATE images based on the provided boolean parameters.
    Each requested segment is extracted individually from a fresh BASE image.
    """
    
    # 1. Define Model & Directory (Self-Contained)
    model_name = "u2net_cloth_seg.onnx"
    model_dir = os.path.join(os.getcwd(), "AI_Models")
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, model_name)
    
    url = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_cloth_seg.onnx"
    
    # 2. Auto-Download if Missing
    if not os.path.exists(model_path):
        print(f"\n📥 Model '{model_name}' missing! Downloading directly to '{model_dir}'...")
        urllib.request.urlretrieve(url, model_path)
        print(f"✅ Download complete!")
            
    # 3. Output Setup
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext = os.path.splitext(base_name)[0]
    
    print(f"\n🤖 Running Levindabhi Segmentation on '{base_name}'...")
    
    try:
        # Load BASE Image
        base_img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if base_img is None: raise ValueError("Cannot read base image")
        h, w = base_img.shape[:2]
        
        # -------------------------------------------------------------
        # 🎯 SMART PARAMETER PARSING (From UI Checkboxes)
        # -------------------------------------------------------------
        valid_tasks = {}
        
        if str(extract_upper_cloth).lower() == 'true':
            valid_tasks["upper_cloth"] = 1
        if str(extract_lower_cloth).lower() == 'true':
            valid_tasks["lower_cloth"] = 2
        if str(extract_full_dress).lower() == 'true':
            valid_tasks["full_dress"] = 3
                
        if not valid_tasks:
            print("⚠️ No clothing parts selected! Please check at least one option in the UI.")
            return image_path
            
        print(f"   ↳ Segments to extract: {', '.join(valid_tasks.keys()).title().replace('_', ' ')}")
        
        # -------------------------------------------------------------
        # 🧠 CORE AI EXECUTION (Runs strictly ONCE)
        # -------------------------------------------------------------
        session = onnxruntime.InferenceSession(model_path, providers=['CPUExecutionProvider', 'CUDAExecutionProvider'])
        
        # Convert 4-channel PNG to 3-channel for AI processing
        if len(base_img.shape) == 3 and base_img.shape[2] == 4:
            ai_input_img = cv2.cvtColor(base_img, cv2.COLOR_BGRA2BGR)
        elif len(base_img.shape) == 2:
            ai_input_img = cv2.cvtColor(base_img, cv2.COLOR_GRAY2BGR)
        else:
            ai_input_img = base_img.copy()

        blob = cv2.dnn.blobFromImage(ai_input_img, 1.0/127.5, (768, 768), (127.5, 127.5, 127.5), swapRB=True, crop=False)
        
        input_name = session.get_inputs()[0].name
        out = session.run(None, {input_name: blob}) 
        
        # Add [0][0] to extract the 3D tensor from ONNXRuntime's list structure
        tensor_out = out[0][0]
        
        ch_offset = 1 if tensor_out.shape[0] == 4 else 0
        
        channels = {
            1: cv2.resize(tensor_out[ch_offset + 0], (w, h)), 
            2: cv2.resize(tensor_out[ch_offset + 1], (w, h)), 
            3: cv2.resize(tensor_out[ch_offset + 2], (w, h))  
        }
        
        saved_files = []

        # -------------------------------------------------------------
        # 🔄 ISOLATED LOOP OVER SELECTIONS
        # -------------------------------------------------------------
        for part_name, cls_id in valid_tasks.items():
            
            raw_mask = (channels[cls_id] > 0.5).astype(np.uint8) * 255
                
            if cv2.countNonZero(raw_mask) == 0:
                print(f"   ⏭️ Skipped '{part_name.title()}' (Not detected in image)")
                continue

            try: offset_val = int(mask_offset)
            except: offset_val = 0
                
            if offset_val > 0:
                kernel = np.ones((offset_val, offset_val), np.uint8)
                raw_mask = cv2.dilate(raw_mask, kernel, iterations=1)
            elif offset_val < 0:
                kernel = np.ones((abs(offset_val), abs(offset_val)), np.uint8)
                raw_mask = cv2.erode(raw_mask, kernel, iterations=1)

            try: blur_val = int(mask_blur)
            except: blur_val = 0
                
            if blur_val > 0:
                if blur_val % 2 == 0: blur_val += 1
                raw_mask = cv2.GaussianBlur(raw_mask, (blur_val, blur_val), 0)

            suffix = f"{part_name}_mask" if str(save_mask_only).lower() == 'true' else part_name
            final_output_path = os.path.join(output_dir, f"{name_without_ext}_{suffix}.png")
            
            if str(save_mask_only).lower() == 'true':
                cv2.imwrite(final_output_path, raw_mask)
            else:
                if len(base_img.shape) == 3 and base_img.shape[2] == 3:
                    fresh_bgra = cv2.cvtColor(base_img, cv2.COLOR_BGR2BGRA)
                elif len(base_img.shape) == 2:
                    fresh_bgra = cv2.cvtColor(base_img, cv2.COLOR_GRAY2BGRA)
                else:
                    fresh_bgra = base_img.copy()
                    
                fresh_bgra[:, :, 3] = raw_mask
                cv2.imwrite(final_output_path, fresh_bgra)
                
            print(f"   ┣━ ✅ Saved {part_name.title().replace('_', ' ')}: {os.path.basename(final_output_path)}")
            saved_files.append(final_output_path)
            
        print(f"🎉 Successfully completed parsing.\n")
        
        return saved_files if len(saved_files) > 1 else (saved_files[0] if saved_files else image_path)

    except Exception as e:
        print(f"❌ Execution failed: {str(e)}")
        return image_path


def u2net_cloth_segmentation(image_path, output_dir, 
                                extract_upper_cloth=True, 
                                extract_lower_cloth=False, 
                                extract_full_dress=False,
                                mask_offset=0, 
                                mask_blur=0, 
                                save_mask_only=False):
    """
    Model Name: u2net_cloth_seg.onnx
    Dedicated advanced clothing segmentation model.
    Extracts Upper, Lower, and Full clothing into separate PNGs.
    """
    
    # 1. Define Model & Directory (Self-Contained)
    model_name = "u2net_cloth_seg.onnx"
    model_dir = os.path.join(os.getcwd(), "AI_Models")
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, model_name)
    
    url = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_cloth_seg.onnx"
    
    # 2. Auto-Download if Missing
    if not os.path.exists(model_path):
        print(f"\n📥 Model '{model_name}' missing! Downloading directly to '{model_dir}'...")
        urllib.request.urlretrieve(url, model_path)
        print(f"✅ Download complete!")
        
    # 3. Output Setup
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext = os.path.splitext(base_name)[0]
    
    print(f"\n🤖 Running Advanced Cloth Segmentation on '{base_name}'...")

    try:
        base_img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if base_img is None: raise ValueError("Cannot read base image")
        h, w = base_img.shape[:2]
        
        # -------------------------------------------------------------
        # 🎯 MAP USER SELECTIONS TO AI CHANNELS
        # -------------------------------------------------------------
        valid_tasks = {}
        
        if str(extract_upper_cloth).lower() == 'true': valid_tasks['upper_cloth'] = 1
        if str(extract_lower_cloth).lower() == 'true': valid_tasks['lower_cloth'] = 2
        if str(extract_full_dress).lower() == 'true':  valid_tasks['full_dress'] = 3
            
        if not valid_tasks:
            print("⚠️ No clothing parts selected in UI! Skipping execution.")
            return image_path
            
        print(f"   ↳ Segments to extract: {', '.join(valid_tasks.keys()).title().replace('_', ' ')}")

        # -------------------------------------------------------------
        # 🧠 CORE AI EXECUTION (Runs ONCE for speed)
        # -------------------------------------------------------------
        net = cv2.dnn.readNetFromONNX(model_path)
        
        blob = cv2.dnn.blobFromImage(base_img, 1.0/127.5, (768, 768), (127.5, 127.5, 127.5), swapRB=True, crop=False)
        net.setInput(blob)
        out = net.forward() 
        
        ch_offset = 1 if out[0].shape[0] == 4 else 0
        saved_files = []

        # -------------------------------------------------------------
        # 🔄 ISOLATED LOOP OVER SELECTIONS (Using Fresh Base Image)
        # -------------------------------------------------------------
        for part_name, channel_idx in valid_tasks.items():
            
            mask_layer = out[0][ch_offset + (channel_idx - 1)]
            mask_resized = cv2.resize(mask_layer, (w, h), interpolation=cv2.INTER_CUBIC)
            raw_mask = (mask_resized > 0.5).astype(np.uint8) * 255
                
            if cv2.countNonZero(raw_mask) == 0:
                print(f"   ⏭️ Skipped '{part_name.title().replace('_', ' ')}' (Not detected in image)")
                continue

            try: offset_val = int(mask_offset)
            except: offset_val = 0
                
            if offset_val > 0:
                kernel = np.ones((offset_val, offset_val), np.uint8)
                raw_mask = cv2.dilate(raw_mask, kernel, iterations=1)
            elif offset_val < 0:
                kernel = np.ones((abs(offset_val), abs(offset_val)), np.uint8)
                raw_mask = cv2.erode(raw_mask, kernel, iterations=1)

            try: blur_val = int(mask_blur)
            except: blur_val = 0
                
            if blur_val > 0:
                if blur_val % 2 == 0: blur_val += 1 
                raw_mask = cv2.GaussianBlur(raw_mask, (blur_val, blur_val), 0)

            suffix = f"{part_name}_mask" if str(save_mask_only).lower() == 'true' else part_name
            final_output_path = os.path.join(output_dir, f"{name_without_ext}_{suffix}.png")
            
            if str(save_mask_only).lower() == 'true':
                cv2.imwrite(final_output_path, raw_mask)
            else:
                if len(base_img.shape) == 3 and base_img.shape[2] == 3:
                    fresh_bgra = cv2.cvtColor(base_img, cv2.COLOR_BGR2BGRA)
                elif len(base_img.shape) == 2:
                    fresh_bgra = cv2.cvtColor(base_img, cv2.COLOR_GRAY2BGRA)
                else:
                    fresh_bgra = base_img.copy()
                    
                fresh_bgra[:, :, 3] = raw_mask
                cv2.imwrite(final_output_path, fresh_bgra)
                
            print(f"   ┣━ ✅ Saved {part_name.title().replace('_', ' ')}: {os.path.basename(final_output_path)}")
            saved_files.append(final_output_path)
            
        print(f"🎉 Successfully completed parsing.\n")
        
        return saved_files if len(saved_files) > 1 else (saved_files[0] if saved_files else image_path)

    except Exception as e:
        print(f"❌ Execution failed: {str(e)}")
        return image_path


def schp_lip_parsing_cloth_segmentation(image_path, output_dir, 
                              extract_upper_cloth=True, 
                              extract_lower_cloth=False, 
                              extract_coat_jacket=False,
                              extract_dress_jumpsuit=False,
                              extract_face_hair=False,
                              extract_accessories=False,
                              extract_shoes_socks=False,
                              extract_body_skin=False,
                              mask_offset=0, 
                              mask_blur=0, 
                              save_mask_only=False):
    """
    Model Name: schp-lip-20.onnx
    Ultra-Advanced Semantic Segmentation (Look Into Person 20-Class Dataset).
    Automatically maps UI checkboxes to exact neural network classes.
    Extracts each component perfectly from an isolated BASE image.
    """
    
    # 1. Exact Original Model Name (DO NOT RENAME THESE FILES IN FOLDER)
    model_name = "schp-lip-20.onnx"
    model_dir = os.path.join(os.getcwd(), "AI_Models")
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, model_name)
    
    # 2. Strict Check for Model Structure & Data File
    if not os.path.exists(model_path):
        print(f"\n⚠️ [AI ENGINE HALTED] Model '{model_name}' is missing!")
        print(f"   Please ensure BOTH '{model_name}' and '{model_name}.data' are inside:")
        print(f"   📂 {model_dir}")
        return image_path
        
    # 3. Output Path & Directory Setup
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext = os.path.splitext(base_name)[0]
    
    print(f"\n🤖 Running Advanced SCHP-LIP Parsing on '{base_name}'...")

    try:
        base_img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if base_img is None: raise ValueError("Cannot read base image")
        h, w = base_img.shape[:2]
        
        # -------------------------------------------------------------
        # 🎯 SMART UI-TO-CLASS MAPPING
        # -------------------------------------------------------------
        valid_tasks = {}
        
        if str(extract_upper_cloth).lower() == 'true': valid_tasks['upper_cloth'] = [5]
        if str(extract_lower_cloth).lower() == 'true': valid_tasks['lower_cloth'] = [9, 12]
        if str(extract_coat_jacket).lower() == 'true': valid_tasks['coat_jacket'] = [7]
        if str(extract_dress_jumpsuit).lower() == 'true': valid_tasks['dress_jumpsuit'] = [6, 10]
        if str(extract_face_hair).lower() == 'true': valid_tasks['face_hair'] = [13, 2]
        if str(extract_accessories).lower() == 'true': valid_tasks['accessories'] = [1, 3, 4, 11]
        if str(extract_shoes_socks).lower() == 'true': valid_tasks['shoes_socks'] = [8, 18, 19]
        if str(extract_body_skin).lower() == 'true': valid_tasks['body_skin'] = [14, 15, 16, 17]
            
        if not valid_tasks:
            print("⚠️ No specific features selected in UI! Skipping execution.")
            return image_path
            
        print(f"   ↳ Processing Modules: {', '.join(valid_tasks.keys()).title().replace('_', ' ')}")

        # -------------------------------------------------------------
        # 🧠 CORE AI EXECUTION (Runs strictly ONCE for performance)
        # -------------------------------------------------------------
        # Switching from OpenCV DNN to ONNXRuntime to bypass the parsing error
        session = onnxruntime.InferenceSession(model_path, providers=['CPUExecutionProvider', 'CUDAExecutionProvider'])
        
        # --- FIX: Convert 4-channel PNG to 3-channel for AI processing ---
        if len(base_img.shape) == 3 and base_img.shape[2] == 4:
            ai_input_img = cv2.cvtColor(base_img, cv2.COLOR_BGRA2BGR)
        elif len(base_img.shape) == 2:
            ai_input_img = cv2.cvtColor(base_img, cv2.COLOR_GRAY2BGR)
        else:
            ai_input_img = base_img.copy()
        # ----------------------------------------------------------------
        
        blob = cv2.dnn.blobFromImage(ai_input_img, 1.0/255.0, (473, 473), (0, 0, 0), swapRB=True, crop=False)
        
        input_name = session.get_inputs()[0].name
        out = session.run(None, {input_name: blob}) 
        
        # --- FIX: Added extra [0] to extract the tensor from the ONNX list ---
        parsed_classes = np.argmax(out[0][0], axis=0).astype(np.uint8)
        parsed_classes = cv2.resize(parsed_classes, (w, h), interpolation=cv2.INTER_NEAREST)
        
        saved_files = []

        # -------------------------------------------------------------
        # 🔄 ISOLATED LOOP OVER SELECTIONS (Using Fresh Base Image)
        # -------------------------------------------------------------
        for part_name, class_ids in valid_tasks.items():
            
            raw_mask = np.zeros((h, w), dtype=np.uint8)
            for cls_id in class_ids:
                raw_mask[parsed_classes == cls_id] = 255
                
            if cv2.countNonZero(raw_mask) == 0:
                print(f"   ⏭️ Skipped '{part_name.title().replace('_', ' ')}' (Not detected in image)")
                continue

            try: offset_val = int(mask_offset)
            except: offset_val = 0
                
            if offset_val > 0:
                kernel = np.ones((offset_val, offset_val), np.uint8)
                raw_mask = cv2.dilate(raw_mask, kernel, iterations=1)
            elif offset_val < 0:
                kernel = np.ones((abs(offset_val), abs(offset_val)), np.uint8)
                raw_mask = cv2.erode(raw_mask, kernel, iterations=1)

            try: blur_val = int(mask_blur)
            except: blur_val = 0
                
            if blur_val > 0:
                if blur_val % 2 == 0: blur_val += 1 
                raw_mask = cv2.GaussianBlur(raw_mask, (blur_val, blur_val), 0)

            suffix = f"{part_name}_mask" if str(save_mask_only).lower() == 'true' else part_name
            final_output_path = os.path.join(output_dir, f"{name_without_ext}_{suffix}.png")
            
            if str(save_mask_only).lower() == 'true':
                cv2.imwrite(final_output_path, raw_mask)
            else:
                if len(base_img.shape) == 3 and base_img.shape[2] == 3:
                    fresh_bgra = cv2.cvtColor(base_img, cv2.COLOR_BGR2BGRA)
                elif len(base_img.shape) == 2:
                    fresh_bgra = cv2.cvtColor(base_img, cv2.COLOR_GRAY2BGRA)
                else:
                    fresh_bgra = base_img.copy()
                    
                fresh_bgra[:, :, 3] = raw_mask
                cv2.imwrite(final_output_path, fresh_bgra)
                
            print(f"   ┣━ ✅ Exported {part_name.title().replace('_', ' ')}: {os.path.basename(final_output_path)}")
            saved_files.append(final_output_path)
            
        print(f"🎉 Engine executed flawlessly.\n")
        
        return saved_files if len(saved_files) > 1 else (saved_files[0] if saved_files else image_path)

    except Exception as e:
        print(f"❌ Execution failed: {str(e)}")
        return image_path


def restore_heavily_damaged_photo(image_path, output_dir, upscale=2):
    """
    Restores old photos with severe physical damage (thick cracks/tears).
    Automatically routes to GPU for processing if available.
    """
    try:
        import torch
        from gfpgan import GFPGANer
    except ImportError:
        raise ImportError("Please install required AI packages: pip install gfpgan realesrgan torch")
        
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Error: The source path '{image_path}' does not exist.")
        
    # --- ISOLATED DOWNLOAD LOGIC ---
    model_dir = os.path.join(os.getcwd(), "AI_Models")
    os.makedirs(model_dir, exist_ok=True)
    
    esrgan_path = os.path.join(model_dir, "RealESRGAN_x2plus.pth")
    if not os.path.exists(esrgan_path):
        print(f"📥 Downloading Real-ESRGAN to {model_dir}...")
        urllib.request.urlretrieve('https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth', esrgan_path)

    gfpgan_path = os.path.join(model_dir, "GFPGANv1.4.pth")
    if not os.path.exists(gfpgan_path):
        print(f"📥 Downloading GFPGAN to {model_dir}...")
        urllib.request.urlretrieve('https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth', gfpgan_path)
    # -------------------------------

    # 1. Output Path Generation
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext, ext = os.path.splitext(base_name)
    ext = ext if ext else '.jpg'
    final_output_path = os.path.join(output_dir, f"{name_without_ext}_fully_restored{ext}")

    # 2. Hardware / GPU Routing
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Hardware Check: Initializing AI Models on {device.type.upper()}")

    # 3. Load Background AI (Real-ESRGAN)
    try:
        from basicsr.archs.rrdbnet_arch import RRDBNet # type: ignore
        from realesrgan import RealESRGANer
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=2)
        
        bg_upsampler = RealESRGANer(
            scale=2, 
            model_path=esrgan_path, # Using forced local path
            model=model, tile=400, tile_pad=10, pre_pad=0, 
            half=(device.type == 'cuda'), 
            device=device
        )
    except ImportError:
        bg_upsampler = None
        print("Warning: Real-ESRGAN not found. Backgrounds will not be enhanced.")

    # 4. Load Face AI (GFPGAN)
    restorer = GFPGANer(
        model_path=gfpgan_path, # Using forced local path
        upscale=upscale, arch='clean', channel_multiplier=2, bg_upsampler=bg_upsampler, device=device
    )

    # 5. Read Image
    input_img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if input_img is None:
        raise ValueError(f"Could not read the image at {image_path}")

    # --- AGGRESSIVE CRACK REPAIR ALGORITHM ---
    print("Executing heavy crack and scratch removal...")
    gray = cv2.cvtColor(input_img, cv2.COLOR_BGR2GRAY)
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (7, 7))
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
    _, crack_mask = cv2.threshold(tophat, 12, 255, cv2.THRESH_BINARY)
    crack_mask = cv2.dilate(crack_mask, np.ones((3, 3), np.uint8), iterations=2)
    input_img = cv2.inpaint(input_img, crack_mask, inpaintRadius=7, flags=cv2.INPAINT_TELEA)
    # -----------------------------------------

    # 6. AI Inference
    print("Repair complete. Handing over to AI for facial enhancement and upscaling...")
    _, _, restored_img = restorer.enhance(
        input_img, 
        has_aligned=False, 
        only_center_face=False, 
        paste_back=True
    )

    # 7. Save the final result
    if restored_img is not None:
        cv2.imwrite(final_output_path, restored_img)
        print(f"Success! Restored photo saved to: {final_output_path}")
        return final_output_path
    else:
        raise RuntimeError("AI Photo restoration failed.")


def enhance_full_image(image_path, output_dir, outscale=4):
    """
    Enhances and upscales ANY general image (objects, landscapes, humans) using Real-ESRGAN.
    Automatically routes to GPU for processing if available.
    """
    try:
        import torch
        from basicsr.archs.rrdbnet_arch import RRDBNet # type: ignore
        from realesrgan import RealESRGANer
    except ImportError:
        raise ImportError("Please install required AI packages: pip install realesrgan torch basicsr")
        
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Error: The source path '{image_path}' does not exist.")
        
    # --- ISOLATED DOWNLOAD LOGIC ---
    model_dir = os.path.join(os.getcwd(), "AI_Models")
    os.makedirs(model_dir, exist_ok=True)
    esrgan_path = os.path.join(model_dir, "RealESRGAN_x4plus.pth")
    if not os.path.exists(esrgan_path):
        print(f"📥 Downloading Real-ESRGAN x4 to {model_dir}...")
        urllib.request.urlretrieve('https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth', esrgan_path)
    # -------------------------------

    # 1. Output Path Generation
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext, ext = os.path.splitext(base_name)
    ext = ext if ext else '.jpg'
    final_output_path = os.path.join(output_dir, f"{name_without_ext}_upscaled{ext}")

    # 2. Hardware / GPU Routing
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Hardware Check: Initializing AI Models on {device.type.upper()}")

    # 3. Load Universal AI Upsampler (Real-ESRGAN x4plus)
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    upsampler = RealESRGANer(
        scale=4, 
        model_path=esrgan_path, # Using forced local path
        model=model, 
        tile=400,          
        tile_pad=10, 
        pre_pad=0, 
        half=(device.type == 'cuda'), 
        device=device
    )

    # 4. Read Image
    input_img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if input_img is None:
        raise ValueError(f"Could not read the image at {image_path}")

    # 5. AI Inference
    print(f"Enhancing and upscaling full image to {outscale}x, please wait...")
    try:
        output_img, _ = upsampler.enhance(input_img, outscale=outscale)
    except RuntimeError as error:
        print(f"Error during AI processing: {error}")
        print("Note: If you got a CUDA Out of Memory error, try lowering the 'tile' parameter from 400 to 200.")
        return None

    # 6. Save the final result
    if output_img is not None:
        cv2.imwrite(final_output_path, output_img)
        print(f"Success! Enhanced photo saved to: {final_output_path}")
        return final_output_path
    else:
        raise RuntimeError("AI Photo enhancement failed.")


def ai_noise_control(image_path, output_dir, action="reduce", noise_strength=25):
    """
    Controls image noise with AI.
    - action="reduce": Uses Real-ESRGAN (AI) to flawlessly remove noise and enhance details.
    - action="add": Uses computational math to add cinematic film grain.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Error: Could not find '{image_path}'")
        
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext, ext = os.path.splitext(base_name)
    ext = ext if ext else '.jpg'
    
    action_name = "ai_denoised" if action == "reduce" else "noisy"
    final_output_path = os.path.join(output_dir, f"{name_without_ext}_{action_name}{ext}")

    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Invalid image file.")
        
    action = action.lower().strip()

    if action == "reduce":
        print("Hardware Check: Initializing AI Denoiser...")
        try:
            import torch
            from basicsr.archs.rrdbnet_arch import RRDBNet # type: ignore
            from realesrgan import RealESRGANer
        except ImportError:
            raise ImportError("Please ensure realesrgan and basicsr are installed.")

        # --- ISOLATED DOWNLOAD LOGIC ---
        model_dir = os.path.join(os.getcwd(), "AI_Models")
        os.makedirs(model_dir, exist_ok=True)
        esrgan_path = os.path.join(model_dir, "RealESRGAN_x4plus.pth")
        if not os.path.exists(esrgan_path):
            print(f"📥 Downloading Real-ESRGAN x4 to {model_dir}...")
            urllib.request.urlretrieve('https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth', esrgan_path)
        # -------------------------------

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
        upsampler = RealESRGANer(
            scale=4, 
            model_path=esrgan_path, # Using forced local path
            model=model, tile=400, tile_pad=10, pre_pad=0, 
            half=(device.type == 'cuda'), device=device
        )
        
        orig_h, orig_w = img.shape[:2]
        print("AI is deeply removing noise and rebuilding details. Please wait...")
        
        ai_img, _ = upsampler.enhance(img, outscale=4)
        final_img = cv2.resize(ai_img, (orig_w, orig_h), interpolation=cv2.INTER_AREA)

    elif action == "add":
        print(f"Adding realistic mathematical film grain (Strength: {noise_strength})...")
        row, col, ch = img.shape
        gauss_noise = np.random.normal(0, noise_strength, (row, col, ch)).astype(np.float32)
        noisy_img = img.astype(np.float32) + gauss_noise
        final_img = np.clip(noisy_img, 0, 255).astype(np.uint8)
        
    else:
        raise ValueError("Invalid action. Please use 'reduce' or 'add'.")

    cv2.imwrite(final_output_path, final_img)
    print(f"Success! Saved to: {final_output_path}")
    return final_output_path


def generate_depth_map(image_path, output_dir, model_type="DPT_Hybrid"):
    """
    Generates a high-quality depth/displacement map using the MiDaS AI model.
    """
    try:
        import torch
    except ImportError:
        raise ImportError("Please install PyTorch: pip install torch torchvision timm")

    # --- ISOLATED DOWNLOAD LOGIC FOR PYTORCH HUB ---
    model_dir = os.path.join(os.getcwd(), "AI_Models")
    os.makedirs(model_dir, exist_ok=True)
    torch_cache_dir = os.path.join(model_dir, "torch_cache")
    os.makedirs(torch_cache_dir, exist_ok=True)
    torch.hub.set_dir(torch_cache_dir)
    # -----------------------------------------------

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Error: The source path '{image_path}' does not exist.")

    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext = os.path.splitext(base_name)[0]
    final_output_path = os.path.join(output_dir, f"{name_without_ext}_displacement.png")

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Hardware Check: Running MiDaS Depth AI on {device.type.upper()}")

    print(f"Loading {model_type} model... (May take a moment to download on the first run)")
    try:
        midas = torch.hub.load("intel-isl/MiDaS", model_type)
        midas.to(device)
        midas.eval() 
        
        midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")
        if model_type == "DPT_Large" or model_type == "DPT_Hybrid":
            transform = midas_transforms.dpt_transform
        else:
            transform = midas_transforms.small_transform
            
    except Exception as e:
        raise RuntimeError(f"Failed to load MiDaS model. Ensure 'timm' is installed. Error: {e}")

    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not read the image at {image_path}")
    
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    input_batch = transform(img_rgb).to(device)

    print("Calculating 3D geometry and depth... Please wait.")
    with torch.no_grad():
        prediction = midas(input_batch)
        prediction = torch.nn.functional.interpolate(
            prediction.unsqueeze(1),
            size=img_rgb.shape[:2],
            mode="bicubic",
            align_corners=False,
        ).squeeze()

    depth_map = prediction.cpu().numpy()
    depth_min = depth_map.min()
    depth_max = depth_map.max()
    
    if depth_max - depth_min > 0:
        depth_normalized = (depth_map - depth_min) / (depth_max - depth_min)
    else:
        depth_normalized = np.zeros_like(depth_map) 
        
    depth_image = (depth_normalized * 255.0).astype(np.uint8)

    cv2.imwrite(final_output_path, depth_image)
    print(f"Success! Displacement map saved to: {final_output_path}")
    
    return final_output_path


def generate_ultra_detailed_depth(image_path, output_dir, quality="base"):
    """
    Generates an ultra-detailed displacement map using Depth Anything V2.
    """
    try:
        import torch
    except ImportError:
        raise ImportError("Please install required packages: pip install transformers torch")

    # --- ISOLATED DOWNLOAD LOGIC FOR HUGGING FACE ---
    model_dir = os.path.join(os.getcwd(), "AI_Models")
    os.makedirs(model_dir, exist_ok=True)
    hf_cache_dir = os.path.join(model_dir, "huggingface_cache")
    os.makedirs(hf_cache_dir, exist_ok=True)
    os.environ["HF_HOME"] = hf_cache_dir
    # Must import pipeline AFTER setting the environment variable
    from transformers import pipeline
    # ------------------------------------------------

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Error: The source path '{image_path}' does not exist.")

    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext = os.path.splitext(base_name)[0]
    final_output_path = os.path.join(output_dir, f"{name_without_ext}_ultra_displacement.png")

    models = {
        "small": "depth-anything/Depth-Anything-V2-Small-hf",
        "base": "depth-anything/Depth-Anything-V2-Base-hf",
        "large": "depth-anything/Depth-Anything-V2-Large-hf"
    }
    model_id = models.get(quality.lower().strip(), models["base"])

    device_id = 0 if torch.cuda.is_available() else -1
    device_name = "GPU (GTX 1650 Ti)" if device_id == 0 else "CPU"
    print(f"Loading Depth Anything V2 ({quality.upper()}) on {device_name}...")
    print("Note: It may take a minute to download the weights on the first run.")

    pipe = pipeline(task="depth-estimation", model=model_id, device=device_id)

    print("Analyzing micro-details and calculating strict geometry...")
    input_image = Image.open(image_path).convert("RGB")

    result = pipe(input_image)
    depth_image = result["depth"]

    depth_array = np.array(depth_image)
    cv2.imwrite(final_output_path, depth_array)
    print(f"Success! Ultra-detailed displacement map saved to: {final_output_path}")

    return final_output_path


def colorize_bw_image(image_path, output_dir):
    """
    Colorizes black and white photos using Zhang's Deep Learning Colorizer.
    100% self-contained. Downloads heavy weights strictly into 'AI_Models/Colorization'.
    Leverages OpenCV DNN and NumPy for extreme stability.
    """
    if not os.path.exists(image_path):
        print(f"❌ Error: Image not found at '{image_path}'")
        return image_path
        
    # 1. Output Path Generation
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext, ext = os.path.splitext(base_name)
    ext = ext if ext else '.jpg'
    final_output_path = os.path.join(output_dir, f"{name_without_ext}_colorized{ext}")

    # 2. Strict Isolated Directory for Colorization Models
    model_dir = os.path.join(os.getcwd(), "AI_Models", "Colorization")
    os.makedirs(model_dir, exist_ok=True)
    
    prototxt_path = os.path.join(model_dir, "colorization_deploy_v2.prototxt")
    caffemodel_path = os.path.join(model_dir, "colorization_release_v2.caffemodel")
    pts_path = os.path.join(model_dir, "pts_in_hull.npy")
    
    # 3. Model URLs
    urls = {
        prototxt_path: "https://raw.githubusercontent.com/richzhang/colorization/caffe/models/colorization_deploy_v2.prototxt",
        pts_path: "https://raw.githubusercontent.com/richzhang/colorization/caffe/resources/pts_in_hull.npy",
        # Reliable HuggingFace mirror for the 120MB Caffemodel
        caffemodel_path: "https://huggingface.co/camenduru/colorization/resolve/main/colorization_release_v2.caffemodel"
    }

    # 4. Smart Download Logic (Checks before downloading)
    print("\n🎨 Hardware Check: Initializing OpenCV Colorization AI...")
    for path, url in urls.items():
        if not os.path.exists(path):
            file_name = os.path.basename(path)
            print(f"📥 Downloading {file_name} into AI_Models... (Please wait)")
            try:
                urllib.request.urlretrieve(url, path)
                print(f"✅ {file_name} downloaded successfully!")
            except Exception as e:
                print(f"❌ Download failed for {file_name}. Error: {e}")
                return image_path

    try:
        # 5. Load the Network in OpenCV
        net = cv2.dnn.readNetFromCaffe(prototxt_path, caffemodel_path)
        pts = np.load(pts_path)

        # 6. Configure Neural Network Layers mathematically
        class8 = net.getLayerId("class8_ab")
        conv8 = net.getLayerId("conv8_313_rh")
        pts = pts.transpose().reshape(2, 313, 1, 1)
        net.getLayer(class8).blobs = [pts.astype("float32")]
        net.getLayer(conv8).blobs = [np.full([1, 313], 2.606, dtype="float32")]
        
        # Try to use CUDA if available in your OpenCV build, fallback to CPU
        try:
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
        except Exception:
            pass 

        # 7. Image Preprocessing (Extract Lightness/L-channel)
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not read image: {image_path}")
            
        scaled = image.astype("float32") / 255.0
        lab = cv2.cvtColor(scaled, cv2.COLOR_BGR2LAB)
        
        resized = cv2.resize(lab, (224, 224))
        L = cv2.split(resized)[0]
        L -= 50  # Mean subtraction required by the model

        # 8. AI Inference (Predict AB color channels)
        print("🧠 AI is injecting historical colors... Please wait.")
        net.setInput(cv2.dnn.blobFromImage(L))
        ab = net.forward()[0, :, :, :].transpose((1, 2, 0))
        
        # 9. Post-processing & Image Reconstruction
        ab = cv2.resize(ab, (image.shape[1], image.shape[0]))
        L_original = cv2.split(lab)[0]
        colorized = np.concatenate((L_original[:, :, np.newaxis], ab), axis=2)
        
        # Convert back to standard BGR color space
        colorized = cv2.cvtColor(colorized, cv2.COLOR_LAB2BGR)
        colorized = np.clip(colorized, 0, 1)
        colorized = (255 * colorized).astype("uint8")

        # 10. Save Output
        cv2.imwrite(final_output_path, colorized)
        print(f"🎉 Success! Colorized photo saved to: {os.path.basename(final_output_path)}")
        return final_output_path

    except Exception as e:
        print(f"❌ Colorization execution failed: {str(e)}")
        return image_path


def siggraph_colorize(image_path, output_dir):
    """
    State-of-the-art realistic colorization (SIGGRAPH17).
    100% Hub-Free, Zip-Free, and Self-Contained Imports.
    Includes an in-memory bypass for the missing IPython dependency.
    """
    # 1. 100% Self-Contained Imports
    import os
    import sys
    import cv2
    import numpy as np
    import urllib.request
    import types
    
    try:
        import torch
    except ImportError:
        raise ImportError("Please install PyTorch: pip install torch")

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Error: The source path '{image_path}' does not exist.")
        
    # 2. Output Setup
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext, ext = os.path.splitext(base_name)
    ext = ext if ext else '.jpg'
    final_output_path = os.path.join(output_dir, f"{name_without_ext}_siggraph_colored{ext}")

    # 3. Strict Local Directory Setup
    ai_models_dir = os.path.join(os.getcwd(), "AI_Models")
    color_dir = os.path.join(ai_models_dir, "Colorization")
    pkg_dir = os.path.join(color_dir, "colorizers") 
    os.makedirs(pkg_dir, exist_ok=True)

    # 4. DIRECT SCRIPT DOWNLOAD (Bypassing torch.hub completely)
    scripts = ["__init__.py", "base_color.py", "eccv16.py", "siggraph17.py", "util.py"]
    base_url = "https://raw.githubusercontent.com/richzhang/colorization/master/colorizers/"

    print("\n📥 Verifying Local AI Scripts...")
    for script in scripts:
        script_path = os.path.join(pkg_dir, script)
        if not os.path.exists(script_path):
            print(f"   ┣━ Downloading core file: {script}...")
            try:
                urllib.request.urlretrieve(base_url + script, script_path)
            except Exception as e:
                print(f"❌ Failed to download {script}: {e}")
                return image_path

    # Add the local directory to system path
    if color_dir not in sys.path:
        sys.path.insert(0, color_dir)

    # 5. IMPORT BYPASS & LOCAL MODULE LOAD
    try:
        # THE FIX: Create a fake IPython module in memory so the script doesn't crash
        if 'IPython' not in sys.modules:
            dummy_ipython = types.ModuleType('IPython')
            dummy_ipython.embed = lambda: None
            sys.modules['IPython'] = dummy_ipython
            
        from colorizers import siggraph17 # type: ignore
    except Exception as e:
        print(f"❌ Local import failed: {e}")
        return image_path

    # 6. Model Weights Download
    model_path = os.path.join(color_dir, "siggraph17.pth")
    model_url = "https://colorizers.s3.us-east-2.amazonaws.com/siggraph17-df00044c.pth"
    
    if not os.path.exists(model_path):
        print(f"📥 Downloading SIGGRAPH17 weights (~115MB) strictly to '{color_dir}'...")
        urllib.request.urlretrieve(model_url, model_path)
        print("✅ SIGGRAPH weights downloaded successfully!")

    print(f"\n🎨 Initializing SIGGRAPH17 Engine in PURE OFFLINE mode...")

    try:
        # 7. Hardware Routing & Model Initialization
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        net = siggraph17(pretrained=False)
        net.load_state_dict(torch.load(model_path, map_location=device))
        net.to(device)
        net.eval()

        # 8. Pure OpenCV Preprocessing
        img_bgr = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise ValueError(f"Could not read image at {image_path}")
            
        h_orig, w_orig = img_bgr.shape[:2]

        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        img_scaled = cv2.resize(img_rgb, (256, 256))
        
        img_scaled_float = img_scaled.astype(np.float32) / 255.0
        img_lab = cv2.cvtColor(img_scaled_float, cv2.COLOR_RGB2LAB)
        
        L_centered = img_lab[:, :, 0] - 50.0  
        l_tensor = torch.from_numpy(L_centered).unsqueeze(0).unsqueeze(0).to(device)

        # 9. AI Inference
        print("🧠 Running neural color prediction...")
        with torch.no_grad():
            out_ab = net(l_tensor).cpu()

        # 10. Post-processing & Recombination
        out_ab_np = out_ab.squeeze(0).numpy().transpose(1, 2, 0)
        out_ab_resized = cv2.resize(out_ab_np, (w_orig, h_orig))
        
        orig_float = img_rgb.astype(np.float32) / 255.0
        orig_lab = cv2.cvtColor(orig_float, cv2.COLOR_RGB2LAB)
        orig_L = orig_lab[:, :, 0]

        final_lab = np.zeros((h_orig, w_orig, 3), dtype=np.float32)
        final_lab[:, :, 0] = orig_L
        final_lab[:, :, 1] = out_ab_resized[:, :, 0]
        final_lab[:, :, 2] = out_ab_resized[:, :, 1]

        final_rgb = cv2.cvtColor(final_lab, cv2.COLOR_LAB2RGB)
        final_bgr = cv2.cvtColor(final_rgb, cv2.COLOR_RGB2BGR)

        final_bgr_uint8 = np.clip(final_bgr * 255.0, 0, 255).astype(np.uint8)

        # 11. Save Result
        cv2.imwrite(final_output_path, final_bgr_uint8)
        print(f"🎉 Success! High-accuracy colorized photo saved to: {final_output_path}")
        return final_output_path

    except Exception as e:
        print(f"❌ SIGGRAPH Colorization failed: {str(e)}")
        return image_path
    

def advanced_ai_inpaint(image_path, mask_path, output_dir):
    """
    State-of-the-art AI Inpainting using LaMa (lama_fp32.onnx).
    FIXED: Robust Masking Logic: Handled Alpha Channel Transparency and Grayscale input seamlessly.
    - Alpha channel? Opaque area (foreground) becomes mask.
    - Grayscale? White area becomes mask.
    """
    # 1. 100% Self-Contained Imports
    import os
    import cv2
    import numpy as np
    import requests  
    
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Error: Image not found at '{image_path}'")
    if not os.path.exists(mask_path):
        raise FileNotFoundError(f"Error: Mask not found at '{mask_path}'. You must provide a valid mask image.")
        
    # 2. Output Setup
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(image_path)
    name_without_ext, ext = os.path.splitext(base_name)
    ext = ext if ext else '.jpg'
    final_output_path = os.path.join(output_dir, f"{name_without_ext}_inpainted{ext}")
    
    # 3. Strict Local Directory Setup
    ai_models_dir = os.path.join(os.getcwd(), "AI_Models")
    inpaint_dir = os.path.join(ai_models_dir, "Inpainting")
    os.makedirs(inpaint_dir, exist_ok=True)
    
    model_name = "lama_fp32.onnx"
    model_path = os.path.join(inpaint_dir, model_name)
    
    if not os.path.exists(model_path):
        print(f"❌ Model not found at {model_path}. Please place lama_fp32.onnx here.")
        return image_path
            
    print(f"\n🪄 Initializing LaMa Inpainting Engine...")
    
    try:
        import onnxruntime as ort
        
        # 4. Hardware Routing
        try:
            available_providers = ort.get_available_providers()
        except Exception:
            available_providers = ['CPUExecutionProvider']
            
        if 'CUDAExecutionProvider' in available_providers:
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            print("   ↳ Hardware: Running on NVIDIA GPU (CUDA)...")
        else:
            providers = ['CPUExecutionProvider']
            print("   ↳ Hardware: Running on CPU (Safe Mode)...")

        session = ort.InferenceSession(model_path, providers=providers)
        
        # 5. --- NEW & ROBUST MASK HANDLING LOGIC ---
        print(f"🧠 Parsing and normalizing mask logic...")
        
        # Read Original High-Res Image normally
        img_bgr = cv2.imread(image_path, cv2.IMREAD_COLOR)
        
        # READ MASK: Use IMREAD_UNCHANGED to check for alpha channel
        mask_raw = cv2.imread(mask_path, cv2.IMREAD_UNCHANGED)
        
        if img_bgr is None or mask_raw is None:
            raise ValueError("Could not read image or mask. Ensure paths are correct.")
        
        h_orig, w_orig = img_bgr.shape[:2]
        
        # --- Logic Begins ---
        if mask_raw.ndim == 3 and mask_raw.shape[2] == 4:
            print("   ┣━ Scenario detected: Input mask has an Alpha channel.")
            # Scenario 1: Alpha channel exists (Transparent pixels)
            alpha_channel = mask_raw[:, :, 3]
            # Convert non-transparent pixels (opaque) to mask foreground (white / 255)
            # Thresholding 0 to handle even faint transparency
            orig_mask_strict = (alpha_channel > 0).astype(np.uint8) * 255 
            
        else:
            print("   ┣━ Scenario detected: Input mask is Grayscale/B&W.")
            # Scenario 2: Simple B&W/Grayscale mask
            if mask_raw.ndim == 3:
                mask_grayscale = cv2.cvtColor(mask_raw, cv2.COLOR_BGR2GRAY)
            else:
                mask_grayscale = mask_raw
                
            # Treat WHITE region as mask foreground (inpaint target)
            orig_mask_strict = (mask_grayscale > 127).astype(np.uint8) * 255
            
        # Ensure strict mask is resized to match the original image exactly
        if (h_orig, w_orig) != orig_mask_strict.shape[:2]:
            orig_mask_strict = cv2.resize(orig_mask_strict, (w_orig, h_orig), interpolation=cv2.INTER_NEAREST)
        
        # --- End of Mask Handling ---
        
       # -----------------------------------------------------------------
        # 6. DYNAMIC RESIZING (Model ke hisaab se size auto-detect karega)
        # -----------------------------------------------------------------
        expected_h, expected_w = session.get_inputs()[0].shape[2:]
        
        # Agar model shape lock nahi hai (dynamic hai), toh 512 use karega
        if not isinstance(expected_h, int): expected_h = 512
        if not isinstance(expected_w, int): expected_w = 512

        img_resized = cv2.resize(img_bgr, (expected_w, expected_h), interpolation=cv2.INTER_AREA)
        mask_resized = cv2.resize(orig_mask_strict, (expected_w, expected_h), interpolation=cv2.INTER_NEAREST)
        
        # 7. TENSORS PRE-PROCESSING
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        img_tensor = (img_rgb / 255.0).astype(np.float32).transpose(2, 0, 1)[np.newaxis, ...]
        mask_tensor = (mask_resized > 127).astype(np.float32)[np.newaxis, np.newaxis, ...]
        
        ort_inputs = {}
        for i in session.get_inputs():
            if "mask" in i.name.lower():
                ort_inputs[i.name] = mask_tensor
            else:
                ort_inputs[i.name] = img_tensor
        
        # 8. AI Inference
        print(f"🧠 AI is analyzing and generating missing background (at {expected_w}x{expected_h})...")
        outputs = session.run(None, ort_inputs)
        
        # 9. POST-PROCESSING (DYNAMIC RANGE HANDLING)
        out_tensor = outputs[0][0]
        out_rgb = out_tensor.transpose(1, 2, 0)
        
        if out_rgb.max() <= 1.01:
            out_rgb = out_rgb * 255.0
            
        out_rgb = np.clip(out_rgb, 0, 255).astype(np.uint8)
        out_bgr_resized = cv2.cvtColor(out_rgb, cv2.COLOR_RGB2BGR)
        
        # 10. Scale AI Output back to High-Res Original
        out_bgr_upscaled = cv2.resize(out_bgr_resized, (w_orig, h_orig), interpolation=cv2.INTER_CUBIC)
        
        # 11. High-Res Blending
        # Only use the AI's generated pixels where the ORIGINAL strict mask is white.
        mask_binary = (orig_mask_strict > 127).astype(np.float32)[..., np.newaxis]
        final_blended = out_bgr_upscaled * mask_binary + img_bgr * (1 - mask_binary)
        
        # 12. Save
        cv2.imwrite(final_output_path, final_blended.astype(np.uint8))
        print(f"🎉 Success! Perfectly in-painted photo saved to: {final_output_path}")
        return final_output_path
        
    except Exception as e:
        print(f"❌ LaMa Inpainting failed: {str(e)}")
        return image_path


 
'''
levindabhi_cloth_segmentation("testImages/levindabhi_cloth_segmentation.jpg", "testImages", 
                                  extract_upper_cloth=True, 
                                  extract_lower_cloth=False, 
                                  extract_full_dress=False,
                                  mask_offset=0, 
                                  mask_blur=0, 
                                  save_mask_only=False)

'''
'''
u2net_cloth_segmentation("testImages/u2net_cloth_segmentation.jpg", "testImages", 
                                extract_upper_cloth=True, 
                                extract_lower_cloth=False, 
                                extract_full_dress=False,
                                mask_offset=0, 
                                mask_blur=0, 
                                save_mask_only=False)
'''
'''
schp_lip_parsing_cloth_segmentation("testImages/advanced_schp_lip_parsing.png", "testImages", 
                              extract_upper_cloth=True, 
                              extract_lower_cloth=False, 
                              extract_coat_jacket=False,
                              extract_dress_jumpsuit=False,
                              extract_face_hair=False,
                              extract_accessories=False,
                              extract_shoes_socks=False,
                              extract_body_skin=False,
                              mask_offset=0, 
                              mask_blur=0, 
                              save_mask_only=False)

'''

# restore_heavily_damaged_photo("testImages/restore_heavily_damaged_photo.png", "testImages", upscale=2)
# enhance_full_image("testImages/enhance_full_image.png", "testImages", outscale=4)
# ai_noise_control("testImages/ai_noise_control.png", "testImages", action="reduce", noise_strength=25)
# generate_depth_map("testImages/generate_depth_map.png", "testImages", model_type="DPT_Hybrid")
# generate_ultra_detailed_depth("testImages/advanced_schp_lip_parsing.png", "testImages", quality="base")
# colorize_bw_image("testImages/grayscale-v1.png", "testImages")
# siggraph_colorize("testImages/grayscale-v1.png", "testImages")
# advanced_ai_inpaint("testImages/download (1).png", "testImages/download (1)_mask.png", "testImages")



# open-cv 5.0.0