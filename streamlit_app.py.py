import streamlit as st
import requests
import time
import io
import base64
from PIL import Image

# ===================== 配置 =====================
API_KEY = st.secrets["SILICONFLOW_API_KEY"]

IMG_API_URL = "https://api.siliconflow.cn/v1/images/generations"
IMG_MODEL = "Kwai-Kolors/Kolors"

VIDEO_SUBMIT_URL = "https://api.siliconflow.cn/v1/video/submit"
VIDEO_STATUS_URL = "https://api.siliconflow.cn/v1/video/status"

# ===================== 辅助函数 =====================
def submit_video_task(prompt, model, image_base64=None):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "image_size": "1280x720"
    }
    if image_base64:
        payload["image"] = image_base64

    response = requests.post(VIDEO_SUBMIT_URL, json=payload, headers=headers, timeout=30)
    if response.status_code != 200:
        raise Exception(f"提交失败（{response.status_code}）：{response.text}")

    result = response.json()
    request_id = result.get("requestId")
    if not request_id:
        raise Exception(f"未返回任务ID")
    return request_id

def get_video_status(request_id):
    try:
        headers = {"Authorization": f"Bearer {API_KEY}"}
        response = requests.get(f"{VIDEO_STATUS_URL}?requestId={request_id}", headers=headers, timeout=10)
        return response.json() if response.status_code == 200 else None
    except:
        return None

# ===================== 页面 =====================
st.set_page_config(page_title="AI 创作工具", layout="centered")
st.title("🎨 AI 创作工具")

# 初始化状态（关键：不写死循环）
if "video_state" not in st.session_state:
    st.session_state.video_state = {
        "request_id": None,
        "status": None,
        "video_url": None,
        "error": None,
        "cancel": False
    }

tab1, tab2 = st.tabs(["📷 文生图", "🎬 文生视频"])

# --------------------- 文生图 ---------------------
with tab1:
    st.subheader("AI 图片生成")
    prompt_img = st.text_area("正向提示词", value="一只可爱的橘猫坐在樱花树下，二次元风格，高清", height=100)
    negative_prompt = st.text_area("反向提示词", value="模糊，低分辨率，丑陋，变形", height=80)
    col1, col2 = st.columns(2)
    with col1:
        size = st.selectbox("尺寸", ["512x512", "768x768", "1024x1024", "1024x768", "1280x720"], index=2)
    with col2:
        steps = st.number_input("步数", 1, 50, 20)

    if st.button("✨ 生成图片", use_container_width=True):
        if not prompt_img.strip():
            st.warning("请输入提示词")
        else:
            with st.spinner("生成中..."):
                try:
                    headers = {"Authorization": f"Bearer {API_KEY}"}
                    payload = {"model": IMG_MODEL, "prompt": prompt_img, "negative_prompt": negative_prompt, "size": size, "num_inference_steps": steps, "n": 1}
                    res = requests.post(IMG_API_URL, json=payload, headers=headers, timeout=60)
                    if res.status_code != 200:
                        st.error(f"API错误：{res.text}")
                    else:
                        img_url = res.json()["data"][0]["url"]
                        img = Image.open(io.BytesIO(requests.get(img_url).content))
                        st.image(img)
                        buf = io.BytesIO()
                        img.save(buf, "PNG")
                        st.download_button("下载图片", buf.getvalue(), "image.png", "image/png")
                except Exception as e:
                    st.error(f"错误：{e}")

# --------------------- 文生视频（无死循环版） ---------------------
with tab2:
    st.subheader("AI 视频生成")
    vs = st.session_state.video_state

    # 正在生成
    if vs["request_id"] and vs["status"] not in ["completed", "failed", "canceled"]:
        st.info("⏳ 视频生成中，每3秒自动刷新")
        progress = st.progress(0)
        data = get_video_status(vs["request_id"])

        if data:
            s = data.get("status")
            p = data.get("progress", 0)
            progress.progress(p / 100, text=f"生成中 {p}%")
            vs["status"] = s
            if s == "completed": vs["video_url"] = data.get("video_url")
            if s == "failed": vs["error"] = data.get("error")

        if st.button("取消生成"):
            vs["cancel"] = True
            vs["status"] = "canceled"
            st.rerun()

        time.sleep(3)
        st.rerun()

    # 已完成
    elif vs["video_url"]:
        st.success("✅ 生成完成")
        st.video(vs["video_url"])
        st.markdown(f"[下载视频]({vs['video_url']})")
        if st.button("生成新视频"):
            st.session_state.video_state = {k:None for k in vs}
            st.session_state.video_state["cancel"]=False
            st.rerun()

    # 失败/取消
    elif vs["error"] or vs["cancel"]:
        msg = vs["error"] if vs["error"] else "已取消"
        st.error(f"❌ {msg}")
        if st.button("重试"):
            st.session_state.video_state = {k:None for k in vs}
            st.session_state.video_state["cancel"]=False
            st.rerun()

    # 初始界面
    else:
        mode = st.radio("模式", ["文本生成视频", "图片生成视频"], horizontal=True)
        prompt = st.text_area("视频描述", height=120)
        img_b64 = None

        if mode == "图片生成视频":
            uploaded = st.file_uploader("上传图片", type=["jpg","png"])
            if uploaded:
                img_b64 = base64.b64encode(uploaded.read()).decode()

        if st.button("🚀 开始生成视频", use_container_width=True):
            if not prompt and mode=="文本生成视频":
                st.warning("请输入描述")
            elif mode=="图片生成视频" and not img_b64:
                st.warning("请上传图片")
            else:
                model = "Wan2.2-T2V-A14B" if mode=="文本生成视频" else "Wan2.2-I2V-A14B"
                try:
                    req_id = submit_video_task(prompt, model, img_b64)
                    vs["request_id"] = req_id
                    vs["status"] = "pending"
                    st.rerun()
                except Exception as e:
                    st.error(f"提交失败：{e}")