import pandas as pd
import json
import time
import re
import sys
from google import genai
from google.genai import types
from difflib import get_close_matches

# ==========================================
# [설정] 본인의 API 키를 입력하세요
# ==========================================
API_KEY = "YOUR_ACTUAL_API_KEY"

def initialize_client(api_key):
    """클라이언트를 초기화하고 사용 가능한 최적의 모델을 자동 선택합니다."""
    try:
        client = genai.Client(api_key=api_key)
        models = client.models.list()
        # 'flash' 모델 중 사용 가능한 첫 번째 모델 선택 (404 방지)
        target = next((m.name for m in models if 'flash' in m.name), "gemini-1.5-flash")
        model_id = target.split('/')[-1]
        return client, model_id
    except Exception as e:
        print(f"❌ 초기화 실패: {e}")
        sys.exit(1)

def get_ai_data(client, model_id, product_name):
    """언어별 특징을 살려 10자 내외의 핵심 효능을 생성합니다."""
    prompt = f"""
    약국 가격표용 10자 내외 핵심 효능 데이터를 생성하세요.
    상품명: '{product_name}'

    [지시사항]
    1. english_name: 영문 브랜드명 위주의 상품명.
    2. chinese_desc: 중국어 간체자로 작성. (예: 缓解消化不良)
    3. japanese_desc: 반드시 히라가나 또는 가타카나를 포함하여 일본어답게 작성. 한자로만 작성 금지. (예: 消化不良の改善)
    """
    
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "english_name": {"type": "STRING"},
                        "chinese_desc": {"type": "STRING"},
                        "japanese_desc": {"type": "STRING"}
                    },
                    "required": ["english_name", "chinese_desc", "japanese_desc"]
                }
            )
        )
        return json.loads(response.text)
    except:
        return {"english_name": product_name, "chinese_desc": "N/A", "japanese_desc": "N/A"}

def clean_name(name):
    """괄호와 공백을 제거하여 매칭률을 극대화합니다."""
    if not isinstance(name, str): return ""
    return re.sub(r'\(.*\)', '', name).replace(" ", "").strip()

def find_qr_id(input_name, list_data):
    """유사도 분석을 통해 최적의 ID를 매칭합니다. 매칭 실패 시 공란을 반환합니다."""
    target = clean_name(input_name)
    lookup = {clean_name(item['name']): item['id'] for item in list_data}
    
    # 1. 완전 일치
    if target in lookup:
        return lookup[target]
    
    # 2. 유사도 매칭 (cutoff 0.3으로 미세한 명칭 차이 허용)
    matches = get_close_matches(target, list(lookup.keys()), n=1, cutoff=0.3)
    if matches:
        return lookup[matches[0]]
    
    # 3. 매칭되는 정보가 없는 경우 공란 반환
    return ""

def main():
    if API_KEY == "YOUR_ACTUAL_API_KEY":
        print("❌ API_KEY를 입력해 주세요.")
        return

    print("🚀 가격표 데이터 생성기 가동 (ID 공란 처리 버전)")
    client, model_id = initialize_client(API_KEY)
    print(f"✅ 모델 연결 성공: {model_id}")

    # 데이터 로드
    try:
        try:
            input_df = pd.read_csv('input.csv', encoding='utf-8-sig')
        except:
            input_df = pd.read_csv('input.csv', encoding='cp949')
            
        with open('list.json', 'r', encoding='utf-8') as f:
            list_data = json.load(f)
    except Exception as e:
        print(f"❌ 파일 로드 실패: {e}")
        return

    results = []
    total = len(input_df)

    for i, row in input_df.iterrows():
        ko_name = str(row['한글상품명']).strip()
        price = row['상품가격']
        
        # ID 매칭 (없을 경우 "")
        qr_id = find_qr_id(ko_name, list_data)
        
        # AI 데이터 생성
        print(f"[{i+1}/{total}] {ko_name} 처리 중...", end="\r")
        ai_info = get_ai_data(client, model_id, ko_name)
        
        # 요청하신 컬럼명으로 데이터 구조 생성
        results.append({
            "한글상품명": ko_name,
            "영어명": ai_info.get("english_name", ko_name),
            "중국어 설명": ai_info.get("chinese_desc", "N/A"),
            "일본어 설명": ai_info.get("japanese_desc", "N/A"),
            "가격": price,
            "QR코드id값": qr_id
        })
        time.sleep(1.5)

    # 결과 저장
    output_df = pd.DataFrame(results)
    output_df.to_csv('output.csv', index=False, encoding='utf-8-sig')
    print(f"\n✨ 완료! 매칭되지 않는 품목은 QR코드id값이 공란으로 처리되었습니다.")

if __name__ == "__main__":
    main()