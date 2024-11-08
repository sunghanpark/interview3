import streamlit as st
import speech_recognition as sr
from difflib import SequenceMatcher
import numpy as np
from datetime import datetime
import threading
import time
import pyaudio
import wave

class AudioRecorder:
    def __init__(self):
        self.is_recording = False
        self.is_paused = False
        self.frames = []
        self.audio = pyaudio.PyAudio()
        self.stream = None
        
    def start_recording(self):
        """녹음을 시작합니다."""
        self.frames = []
        self.is_recording = True
        self.is_paused = False
        
        def record():
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                input=True,
                frames_per_buffer=1024
            )
            
            while self.is_recording:
                if not self.is_paused:
                    data = self.stream.read(1024)
                    self.frames.append(data)
                else:
                    time.sleep(0.1)
                    
        self.record_thread = threading.Thread(target=record)
        self.record_thread.start()
        
    def pause_recording(self):
        """녹음을 일시중지합니다."""
        self.is_paused = True
        
    def resume_recording(self):
        """녹음을 재개합니다."""
        self.is_paused = False
        
    def stop_recording(self):
        """녹음을 종료하고 오디오 파일을 저장합니다."""
        self.is_recording = False
        self.record_thread.join()
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        # 임시 WAV 파일로 저장
        wf = wave.open("temp_recording.wav", 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(44100)
        wf.writeframes(b''.join(self.frames))
        wf.close()
        
        return "temp_recording.wav"

def calculate_similarity(text1, text2):
    """두 텍스트 간의 유사도를 계산합니다."""
    return SequenceMatcher(None, text1, text2).ratio()

def get_feedback(student_answer, model_answer, similarity_threshold=0.7):
    """학생의 답변을 분석하고 피드백을 생성합니다."""
    similarity = calculate_similarity(student_answer.lower(), model_answer.lower())
    
    feedback = {
        "similarity": round(similarity * 100, 2),
        "strengths": [],
        "improvements": []
    }
    
    model_keywords = set(model_answer.lower().split())
    student_keywords = set(student_answer.lower().split())
    
    used_keywords = student_keywords.intersection(model_keywords)
    missing_keywords = model_keywords - student_keywords
    
    if similarity >= similarity_threshold:
        feedback["strengths"].append("답변이 모범 답안과 매우 유사합니다.")
        feedback["strengths"].append(f"핵심 키워드 {len(used_keywords)}개를 잘 사용하였습니다.")
    else:
        feedback["improvements"].append("답변의 구조를 모범 답안과 더 유사하게 개선해보세요.")
        
    if missing_keywords:
        feedback["improvements"].append(f"다음 키워드들을 포함시켜보세요: {', '.join(missing_keywords)}")
    
    return feedback

def process_audio_file(file_path):
    """오디오 파일을 텍스트로 변환합니다."""
    recognizer = sr.Recognizer()
    with sr.AudioFile(file_path) as source:
        audio = recognizer.record(source)
        try:
            text = recognizer.recognize_google(audio, language='ko-KR')
            return text
        except sr.UnknownValueError:
            st.error("음성을 인식하지 못했습니다. 다시 시도해주세요.")
            return None
        except sr.RequestError:
            st.error("음성 인식 서비스에 접근할 수 없습니다.")
            return None

def main():
    st.title("🎤 음성 기반 학습 피드백 시스템")
    
    # 세션 상태 초기화
    if 'history' not in st.session_state:
        st.session_state.history = []
    if 'recorder' not in st.session_state:
        st.session_state.recorder = None
    if 'recording_state' not in st.session_state:
        st.session_state.recording_state = "stopped"  # "stopped", "recording", "paused"
    
    # 사이드바에 모범 답안 입력
    with st.sidebar:
        st.header("📝 모범 답안 설정")
        model_answer = st.text_area(
            "모범 답안을 입력하세요:",
            value="인공지능은 인간의 학습능력과 추론능력, 지각능력, 자연언어의 이해능력 등을 컴퓨터 프로그램으로 실현한 기술입니다."
        )
        
        st.header("⚙️ 설정")
        similarity_threshold = st.slider(
            "유사도 임계값",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            help="이 값 이상의 유사도를 가질 때 답변이 충분히 유사하다고 판단합니다."
        )
    
    # 메인 영역
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("🎙️ 음성 녹음")
        
        # 녹음 컨트롤 버튼들
        col_rec, col_pause, col_stop = st.columns(3)
        
        with col_rec:
            if st.button("녹음 시작", disabled=st.session_state.recording_state == "recording"):
                st.session_state.recorder = AudioRecorder()
                st.session_state.recorder.start_recording()
                st.session_state.recording_state = "recording"
                st.rerun()
        
        with col_pause:
            if st.button("일시정지", disabled=st.session_state.recording_state not in ["recording", "paused"]):
                if st.session_state.recording_state == "recording":
                    st.session_state.recorder.pause_recording()
                    st.session_state.recording_state = "paused"
                else:
                    st.session_state.recorder.resume_recording()
                    st.session_state.recording_state = "recording"
                st.rerun()
        
        with col_stop:
            if st.button("녹음 종료", disabled=st.session_state.recording_state == "stopped"):
                if st.session_state.recorder:
                    audio_file = st.session_state.recorder.stop_recording()
                    student_answer = process_audio_file(audio_file)
                    
                    if student_answer:
                        st.success("음성이 텍스트로 변환되었습니다!")
                        
                        # 피드백 생성
                        feedback = get_feedback(student_answer, model_answer, similarity_threshold)
                        
                        # 기록 저장
                        st.session_state.history.append({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "student_answer": student_answer,
                            "feedback": feedback
                        })
                        
                        # 결과 표시
                        st.write("### 당신의 답변:")
                        st.write(student_answer)
                        
                        st.write(f"### 유사도: {feedback['similarity']}%")
                        
                        if feedback['strengths']:
                            st.write("### 잘한 점 👍")
                            for strength in feedback['strengths']:
                                st.write(f"- {strength}")
                        
                        if feedback['improvements']:
                            st.write("### 개선할 점 💪")
                            for improvement in feedback['improvements']:
                                st.write(f"- {improvement}")
                    
                    st.session_state.recording_state = "stopped"
                    st.session_state.recorder = None
                    st.rerun()
        
        # 현재 녹음 상태 표시
        if st.session_state.recording_state == "recording":
            st.write("🔴 녹음 중...")
        elif st.session_state.recording_state == "paused":
            st.write("⏸️ 일시정지됨")
    
    with col2:
        st.header("📊 학습 기록")
        if st.session_state.history:
            for entry in reversed(st.session_state.history):
                with st.expander(f"📝 {entry['timestamp']}"):
                    st.write("**답변:**")
                    st.write(entry['student_answer'])
                    st.write(f"**유사도:** {entry['feedback']['similarity']}%")
                    
                    if entry['feedback']['strengths']:
                        st.write("**잘한 점:**")
                        for strength in entry['feedback']['strengths']:
                            st.write(f"- {strength}")
                    
                    if entry['feedback']['improvements']:
                        st.write("**개선할 점:**")
                        for improvement in entry['feedback']['improvements']:
                            st.write(f"- {improvement}")
        else:
            st.info("아직 기록이 없습니다. 첫 번째 답변을 녹음해보세요!")

if __name__ == "__main__":
    main()