from rembg import remove
from PIL import Image
import io

def remove_background(input_path, output_path):
    try:
        with open(input_path, 'rb') as i:
            input_image = i.read()
        
        output_image = remove(input_image)
        
        with open(output_path, 'wb') as o:
            o.write(output_image)
            
        print(f"تمت العملية بنجاح! الصورة المحفوظة في: {output_path}")
        
    except Exception as e:
        print(f"حدث خطأ: {e}")

input_img = 'logo_input.png' 
output_img = 'logo.png'

remove_background(input_img, output_img)