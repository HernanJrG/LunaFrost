import os
import re
import requests

DATA_DIR = 'data'

def get_user_images_dir(user_id):
    """Get path to user's images directory"""
    return os.path.join(DATA_DIR, 'users', user_id, 'images')

def download_image(image_url, user_id, overwrite=False):
    """Download image and save it locally, return local path"""
    try:
        filename = os.path.basename(image_url.split('?')[0])
        if not filename:
            from datetime import datetime
            filename = f"image_{datetime.now().timestamp()}.jpg"
        
        safe_filename = re.sub(r'[^\w\.-]', '_', filename)
        images_dir = get_user_images_dir(user_id)
        local_path = os.path.join(images_dir, safe_filename)
        
        if overwrite or not os.path.exists(local_path):
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://novelpia.com/'
            }
            
            response = requests.get(image_url, headers=headers, timeout=10)
            if response.status_code == 200:
                with open(local_path, 'wb') as f:
                    f.write(response.content)
        
        return safe_filename
    except Exception as e:
        return None

def extract_images_from_content(content, user_id):
    """Extract image URLs from content and download them"""
    images = []
    
    image_patterns = [
        r'//images\.novelpia\.com/imagebox/cover/[^\s<>"\']+',
        r'https?://images\.novelpia\.com/imagebox/cover/[^\s<>"\']+',
    ]
    
    for pattern in image_patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            img_url = match.group(0)
            local_filename = download_image(img_url, user_id)
            if local_filename:
                images.append({
                    'url': img_url,
                    'local_path': local_filename,
                    'position': match.start()
                })
    
    return images

def delete_images_for_chapter(chapter, user_id):
    """Delete all images associated with a chapter"""
    if not chapter or not chapter.get('images'):
        return
    
    images_dir = get_user_images_dir(user_id)
    
    for img in chapter['images']:
        img_path = os.path.join(images_dir, img.get('local_path', ''))
        if os.path.exists(img_path):
            try:
                os.remove(img_path)
            except Exception as e:
                pass  # Silently ignore deletion errors

def delete_images_for_novel(novel, user_id):
    """Delete all images associated with a novel"""
    if not novel or not novel.get('chapters'):
        return
    
    for chapter in novel['chapters']:
        if chapter:
            delete_images_for_chapter(chapter, user_id)


def download_images_parallel(image_data_list, user_id, max_workers=5):
    """
    Download multiple images in parallel using ThreadPoolExecutor.
    
    Args:
        image_data_list: List of dicts with 'url' and optional 'alt' keys
        user_id: User ID for storage
        max_workers: Maximum number of parallel downloads (default: 5)
    
    Returns:
        List of image dicts with 'url', 'local_path', and 'alt' keys
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    if not image_data_list:
        return []
    
    images = []
    
    def download_single_image(img_data):
        """Helper function to download a single image"""
        img_url = img_data.get('url', '')
        if not img_url:
            return None
        
        local_filename = download_image(img_url, user_id)
        if local_filename:
            return {
                'url': img_url,
                'local_path': local_filename,
                'alt': img_data.get('alt', 'Chapter Image')
            }
        return None
    
    # Download images in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all download tasks
        future_to_img = {executor.submit(download_single_image, img_data): img_data 
                        for img_data in image_data_list}
        
        # Collect results as they complete
        for future in as_completed(future_to_img):
            try:
                result = future.result()
                if result:
                    images.append(result)
            except Exception as e:
                pass  # Silently ignore download errors
                img_data = future_to_img[future]
    
    return images

