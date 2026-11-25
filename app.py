import streamlit as st
from google import genai
from google.genai import types
import json

# 페이지 기본 설정 (넓은 2열 레이아웃 적용)
st.set_page_config(
    page_title="쓰싹쓰싹 - AI 분리배출 도우미",
    page_icon="♻️",
    layout="wide"
)

# 제공된 기본 데이터
MATERIALS = {
    "PET": {"name": "PET", "category": "플라스틱"},
    "HDPE": {"name": "HDPE", "category": "플라스틱"},
    "LDPE": {"name": "LDPE", "category": "비닐류"},
    "PP": {"name": "PP", "category": "플라스틱"},
    "PS": {"name": "PS", "category": "플라스틱"},
    "PVC": {"name": "PVC", "category": "플라스틱"},
    "종이": {"name": "종이", "category": "종이류"},
    "종이팩": {"name": "종이팩", "category": "종이팩"},
    "유리": {"name": "유리", "category": "유리병"},
    "철": {"name": "철", "category": "금속류"},
    "알루미늄": {"name": "알루미늄", "category": "금속류"},
    "OTHER": {"name": "복합/기타 재질", "category": "제품별 확인"}
}

ITEMS = {
    "페트병": {
        "keywords": ["페트병", "생수병", "생수", "음료수병"],
        "material": "PET",
        "waste_type": "플라스틱",
        "method": "내용물을 비우고 라벨을 제거한 뒤 압착하여 배출합니다."
    },
    "플라스틱 용기": {
        "keywords": ["플라스틱용기", "플라스틱", "용기"],
        "material": "PP",
        "waste_type": "플라스틱",
        "method": "내용물을 비우고 세척한 뒤 다른 재질의 부착물을 제거하여 배출합니다."
    },
    "세제통": {
        "keywords": ["세제", "세제통", "세탁세제", "주방세제"],
        "material": "HDPE",
        "waste_type": "플라스틱",
        "method": "내용물을 비우고 깨끗하게 세척한 뒤 플라스틱류로 배출합니다."
    },
    "비닐": {
        "keywords": ["비닐", "비닐봉투", "비닐봉지", "필름"],
        "material": "LDPE",
        "waste_type": "비닐류",
        "method": "내용물과 이물질을 제거한 뒤 비닐류로 배출합니다."
    },
    "우유팩": {
        "keywords": ["우유팩", "두유팩", "주스팩", "종이팩", "멸균팩"],
        "material": "종이팩",
        "waste_type": "종이팩",
        "method": "내용물을 비우고 헹군 뒤 펼쳐서 말린 후 종이팩으로 배출합니다."
    },
    "종이": {
        "keywords": ["종이", "신문", "신문지", "종이상자", "택배상자", "박스"],
        "material": "종이",
        "waste_type": "종이류",
        "method": "테이프와 비닐 등을 제거하고 깨끗하게 접어서 종이류로 배출합니다."
    },
    "유리병": {
        "keywords": ["유리병", "소주병", "맥주병", "음료수병", "유리"],
        "material": "유리",
        "waste_type": "유리병",
        "method": "내용물을 비우고 세척한 뒤 유리병류로 배출합니다."
    },
    "캔": {
        "keywords": ["캔", "철캔", "통조림"],
        "material": "철",
        "waste_type": "금속류",
        "method": "내용물을 비우고 세척한 뒤 금속류로 배출합니다."
    },
    "알루미늄캔": {
        "keywords": ["알루미늄캔", "맥주캔", "음료캔"],
        "material": "알루미늄",
        "waste_type": "금속류",
        "method": "내용물을 비우고 세척한 뒤 금속류로 배출합니다."
    },
    "건전지": {
        "keywords": ["건전지", "폐건전지", "배터리"],
        "material": "OTHER",
        "waste_type": "폐건전지",
        "method": "일반 쓰레기와 섞지 말고 폐건전지 전용 수거함에 배출합니다."
    },
    "스티로폼": {
        "keywords": ["스티로폼", "완충재", "발포폴리스티렌"],
        "material": "PS",
        "waste_type": "플라스틱",
        "method": "내용물과 테이프 등을 제거하고 깨끗한 경우 분리배출합니다."
    }
}

# Gemini API 클라이언트 초기화 (Streamlit Secrets 사용)
@st.cache_resource
def get_gemini_client():
    if "GEMINI_API_KEY" in st.secrets:
        return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    return None

# 1단계: 로컬 데이터(ITEMS)에서 먼저 검색
def search_local_items(query: str):
    clean_query = query.replace(" ", "").lower()
    if not clean_query:
        return []
    
    results = []
    for name, info in ITEMS.items():
        clean_name = name.replace(" ", "").lower()
        if (clean_query in clean_name or clean_name in clean_query or
            any(clean_query in k.replace(" ", "").lower() or k.replace(" ", "").lower() in clean_query for k in info["keywords"])):
            mat_name = MATERIALS.get(info["material"], {}).get("name", info["material"])
            results.append({
                "name": name,
                "material": mat_name,
                "waste_type": info["waste_type"],
                "method": info["method"],
                "source": "기본 데이터"
            })
    return results

# 2단계: 데이터에 없는 품목은 Gemini AI로 분류
def search_with_ai(query: str):
    client = get_gemini_client()
    if not client:
        return None, "Streamlit Secrets에 `GEMINI_API_KEY`가 설정되지 않았습니다."

    prompt = f"""
    대한민국 환경부 분리배출 가이드라인을 기준으로 다음 쓰레기 품목의 배출 방법을 알려줘.
    입력 품목: "{query}"

    반드시 아래 JSON 형식으로만 응답해:
    {{
        "name": "정확한 품목명",
        "material": "주요 재질 (예: PET, PP, 종이, 유리, 복합재질 등)",
        "waste_type": "분리배출 분류 (예: 플라스틱, 비닐류, 일반쓰레기(종량제), 음식물쓰레기, 전용수거함 등)",
        "method": "구체적인 분리배출 방법을 한두 문장으로 명확하게 설명"
    }}
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
        )
        data = json.loads(response.text)
        data["source"] = "AI 분석"
        return data, None
    except Exception as e:
        return None, f"AI 분석 중 오류가 발생했습니다: {e}"

# 세션 상태 초기화 (우측 칩 버튼 클릭 연동용)
if "search_query" not in st.session_state:
    st.session_state.search_query = ""

def set_query(item_name):
    st.session_state.search_query = item_name

# ================= UI 레이아웃 구성 (스케치 반영) =================
left_col, right_col = st.columns([1.2, 1], gap="large")

# [좌측 영역]: 제목 + 검색창 + 결과창
with left_col:
    st.markdown("# ♻️ 쓰싹쓰싹")
    st.caption("어떤 쓰레기든 입력하면 분리배출 방법을 알려드립니다.")

    # 검색 입력창
    query = st.text_input(
        "분리배출 종류 입력",
        value=st.session_state.search_query,
        placeholder="예: 생수병, 치킨뼈, 영수증, 깨진 유리컵, 아이스팩...",
        label_visibility="collapsed"
    )

    st.markdown("---")

    # 결과 출력 영역
    if query.strip():
        local_results = search_local_items(query)

        if local_results:
            st.success(f"**'{query}'**에 대한 검색 결과 ({len(local_results)}건)")
            for item in local_results:
                with st.container(border=True):
                    st.subheader(f"{item['name']}  `{item['waste_type']}`")
                    st.write(f"**주요 재질:** {item['material']}")
                    st.write(f"**배출 방법:** {item['method']}")
        else:
            # 로컬 데이터에 없으면 AI 호출
            with st.spinner(f"AI가 '{query}'의 분리배출 방법을 분석하고 있습니다..."):
                ai_result, error_msg = search_with_ai(query)

            if error_msg:
                st.error(error_msg)
            elif ai_result:
                st.info(f"✨ AI가 분석한 **'{query}'** 분리배출 가이드입니다.")
                with st.container(border=True):
                    st.subheader(f"{ai_result['name']}  `{ai_result['waste_type']}`")
                    st.write(f"**주요 재질:** {ai_result['material']}")
                    st.write(f"**배출 방법:** {ai_result['method']}")
    else:
        with st.container(border=True):
            st.markdown(
                "<div style='text-align: center; color: gray; padding: 40px 0;'>"
                "검색창에 쓰레기 이름을 입력하거나<br>우측 목록에서 품목을 클릭해 보세요."
                "</div>",
                unsafe_allow_html=True
            )

# [우측 영역]: 제미나이 마음대로 (4대 원칙 + 빠른 품목 선택 버튼)
with right_col:
    with st.container(border=True):
        st.subheader("🌱 올바른 분리배출 4대 원칙")
        st.markdown("""
        1. **비운다:** 용기 안의 내용물은 깨끗이 비우기
        2. **헹군다:** 이물질, 음식물 등은 물로 씻어서 배출하기
        3. **분리한다:** 라벨, 뚜껑 등 다른 재질은 제거하기
        4. **섞지 않는다:** 종류별, 재질별로 구분하여 배출하기
        """)

    with st.container(border=True):
        st.subheader("📦 기본 등록 품목 빠른 보기")
        st.caption("버튼을 누르면 좌측에서 바로 배출 방법을 확인할 수 있습니다.")
        
        # 3열 버튼 그리드 생성
        item_keys = list(ITEMS.keys())
        btn_cols = st.columns(3)
        for idx, key in enumerate(item_keys):
            with btn_cols[idx % 3]:
                st.button(
                    key,
                    key=f"btn_{key}",
                    use_container_width=True,
                    on_click=set_query,
                    args=(key,)
                )
