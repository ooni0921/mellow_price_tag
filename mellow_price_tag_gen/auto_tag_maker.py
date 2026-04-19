import pandas as pd
import qrcode
from PIL import Image, ImageDraw, ImageFont, JpegImagePlugin # 에러 방지용 임포트 유지
import os

# ==========================================
# [사용자 설정 영역]
# ==========================================
FONT_PATH = "NotoSansCJK-Regular.ttc"  # 폰트 경로 확인 필수!
INPUT_CSV = "input.csv"
TAG_DIR = "temp_tags"
FINAL_PDF = "mellow_print_ready.pdf"
BASE_URL = "https://ooni0921.github.io/mellow-pharmacy/?id="

# 300 DPI 기준 규격 (6cm x 3.8cm)
WIDTH, HEIGHT = 708, 448
A4_W, A4_H = 2480, 3508

# ==========================================
# [기능 함수]
# ==========================================

def draw_text_with_scaling(draw, text, position, font_path, initial_size, max_width, fill=(0,0,0)):
    """글자 길이에 따라 크기를 자동으로 조절"""
    current_size = initial_size
    font = ImageFont.truetype(font_path, current_size)
    
    # 텍스트가 숫자인 경우를 대비해 문자열로 변환
    display_text = str(text) if pd.notnull(text) else ""
    
    while draw.textlength(display_text, font=font) > max_width and current_size > 16:
        current_size -= 2
        font = ImageFont.truetype(font_path, current_size)
    draw.text(position, display_text, font=font, fill=fill)

def create_tag_image(row):
    """CSV 데이터를 바탕으로 가격표 이미지 1개 생성"""
    img = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    margin_left = 45
    max_text_w = 410

    # 1. 한글상품명 (CSV 컬럼명 일치)
    draw_text_with_scaling(draw, row['한글상품명'], (margin_left, 50), FONT_PATH, 48, max_text_w)
    
    # 2. 영어명
    draw_text_with_scaling(draw, row['영어명'], (margin_left, 110), FONT_PATH, 26, max_text_w, fill=(80, 80, 80))
    
    # 3. 중국어 설명 / 일본어 설명
    sub_y = 160
    draw_text_with_scaling(draw, row['중국어 설명'], (margin_left, sub_y), FONT_PATH, 22, max_text_w, fill=(120, 120, 120))
    draw_text_with_scaling(draw, row['일본어 설명'], (margin_left, sub_y + 35), FONT_PATH, 22, max_text_w, fill=(120, 120, 120))

    # 4. 가격 (콤마 처리)
    price_val = str(row['가격'])
    if price_val.replace(',', '').isdigit():
        price_val = format(int(price_val.replace(',', '')), ',')
    price_font = ImageFont.truetype(FONT_PATH, 65)
    draw.text((margin_left, 310), f"₩{price_val}", font=price_font, fill=(0, 0, 0))

    # 5. QR 코드 생성 (id 결합)
    full_url = f"{BASE_URL}{row['QR코드id값']}"
    qr = qrcode.QRCode(box_size=6, border=1)
    qr.add_data(full_url)
    qr.make(fit=True)
    qr_img = qr.make_image().convert('RGB').resize((180, 180))
    img.paste(qr_img, (470, 110))
    
    # 안내 문구
    detail_font = ImageFont.truetype(FONT_PATH, 18)
    draw.text((490, 300), "상품 상세 정보", font=detail_font, fill=(34, 139, 34))

    if not os.path.exists(TAG_DIR): os.makedirs(TAG_DIR)
    file_path = f"{TAG_DIR}/{str(row['QR코드id값'])}.png"
    img.save(file_path)
    return file_path

def generate_pdf(image_paths):
    """A4 규격에 맞게 배치"""
    pages = []
    cols, rows = 3, 7
    margin_x = (A4_W - (WIDTH * cols)) // 2
    margin_y = (A4_H - (HEIGHT * rows)) // 2

    current_page = Image.new("RGB", (A4_W, A4_H), (255, 255, 255))
    draw = ImageDraw.Draw(current_page)

    for idx, path in enumerate(image_paths):
        i = idx % 21
        if i == 0 and idx > 0:
            pages.append(current_page)
            current_page = Image.new("RGB", (A4_W, A4_H), (255, 255, 255))
            draw = ImageDraw.Draw(current_page)

        c, r = i % cols, i // cols
        px, py = margin_x + (c * WIDTH), margin_y + (r * HEIGHT)
        
        tag_img = Image.open(path)
        current_page.paste(tag_img, (px, py))
        draw.rectangle([px, py, px + WIDTH, py + HEIGHT], outline=(220, 220, 220), width=1)

    pages.append(current_page)
    pages[0].save(FINAL_PDF, save_all=True, append_images=pages[1:])

# ==========================================
# [실행 메인]
# ==========================================
if __name__ == "__main__":
    print("CSV 데이터를 읽어 가격표 생성을 시작합니다...")
    try:
        # 한글 깨짐 방지를 위해 utf-8-sig 권장
        df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig') 
        
        print("1. 개별 이미지 생성 중...")
        tag_paths = [create_tag_image(row) for _, row in df.iterrows()]
        
        print("2. A4 PDF 합치기 및 칼선 작업 중...")
        generate_pdf(tag_paths)
        
        print(f"\n성공! '{FINAL_PDF}' 파일이 생성되었습니다.")
    except FileNotFoundError:
        print(f"에러: '{INPUT_CSV}' 파일을 찾을 수 없습니다.")
    except KeyError as e:
        print(f"에러: CSV 파일에 {e} 컬럼이 없습니다. 컬럼명을 확인해 주세요.")
    except Exception as e:
        print(f"기타 오류 발생: {e}")