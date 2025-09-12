"""
설정 파일
IP 제한 및 보안 설정
"""

import ipaddress
import os

# 허용된 IP 대역 설정
# 모든 IP에서 접속 허용
ALLOWED_IPS = [
    # 모든 IP 대역 허용
    ipaddress.ip_network('0.0.0.0/0'),           # 모든 IPv4 주소
    ipaddress.ip_network('::/0'),                # 모든 IPv6 주소
]

# 관리자 계정 정보 (환경 변수에서 가져오기)
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'MSE3105')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'KHU')

# 데이터베이스 설정
# Render에서는 PostgreSQL, 로컬에서는 SQLite 사용
DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///budget_management.db')

# 보안 설정 (환경 변수에서 가져오기)
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')

# SSL 설정
SSL_CERT_PATH = 'cert.pem'
SSL_KEY_PATH = 'key.pem'

# 서버 설정
HOST = '0.0.0.0'  # 모든 인터페이스에서 접근 허용
PORT = 8000       # 국제캠퍼스 포트 설정
DEBUG = True

# 허용된 쇼핑몰 목록
ALLOWED_STORES = [
    '시그마알드리치',
    '4science', 
    '디바이스마트',
    '기타',
    '아마존',
    '쿠팡',
    'G마켓'
]

# 쇼핑몰 링크
STORE_LINKS = {
    '시그마알드리치': 'https://www.sigmaaldrich.com/KR/ko',
    '4science': 'https://4science.net/',
    '디바이스마트': 'https://www.devicemart.co.kr/',
    '아마존': 'https://www.amazon.com/',
    '쿠팡': 'https://www.coupang.com/',
    'G마켓': 'https://www.gmarket.co.kr/'
}
