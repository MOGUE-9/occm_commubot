#!/usr/bin/python3
# -*- coding: utf-8 -*-
import re
import os
import requests
import json
from mastodon import Mastodon
from mastodon.streaming import StreamListener
from google.oauth2 import service_account
import gspread
from pyjosa.josa import Josa
from dotenv import load_dotenv
load_dotenv()

# 구글시트 세팅
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file",
         "https://www.googleapis.com/auth/drive"]

creds = service_account.Credentials.from_service_account_file(f'{os.getcwd()}/key.json')
creds = creds.with_scopes(scope)
gc = gspread.authorize(creds)
sh = gc.open_by_url(os.getenv('https://docs.google.com/spreadsheets/d/1fHDl8hJPwbEOeiBRfD7w3AV6UwbOC_d3Pma5J29dmnA/edit?usp=sharing'))
search = sh.worksheet(os.getenv('조사'))
default_visibility = os.getenv('private')
#admin_handle = os.getenv('BOT_ADMIN_HANDLE') #어디에 들어가는 기능인지 모르겠어서 주석처리
#tag_admin = os.getenv('BOT_TAG_ADMIN') == 'true' # 22

BASE = os.getenv('https://occm.cc/')

m = Mastodon(
    client_id=os.getenv('1jTdRbpw5YsK-CvSL3pWcAxKJL258sCP53ms-rLnnrM'),
    client_secret=os.getenv('1icx-lf6qK6hOVTuuN9BhVQpbKG6fbYnoor6FuLVkQo'),
    access_token=os.getenv('qSYDVbVsHOyfFK2_-1X0UTNypTpo3B98HiuewcP2y3U'),
    api_base_url=BASE
)
bot = m.me()

print(f"성공적으로 계정 {bot.username}으로 로그인 되었습니다.")

CLEANR = re.compile('<.*?>')
SEC_CLEANR = re.compile('\B@\w+')

def gettext(raw_html):
    """
    주어진 문자열에서 HTML 태그 및 멘션을 제거하고 정제된 텍스트를 반환합니다.

    Parameters:
        raw_html (str): HTML 태그가 포함된 원본 문자열

    Returns:
        str: HTML 태그 및 멘션이 제거된 정제된 텍스트
    """
    cleantext = re.sub(CLEANR, '', raw_html)
    cleantext = re.sub(SEC_CLEANR, '', cleantext)
    return cleantext

def cleanhtml(raw_html):
    """
    주어진 문자열에서 HTML 태그를 제거하고 정제된 텍스트를 반환합니다.

    Parameters:
        raw_html (str): HTML 태그가 포함된 원본 문자열

    Returns:
        str: HTML 태그가 제거된 정제된 텍스트
    """
    cleantext = re.sub(CLEANR, '', raw_html)
    return cleantext

def getkey(toot_body):
    """
    주어진 문자열에서 [ ] 사이의 키워드를 추출하여 반환합니다.

    Parameters:
        toot_body (str): 키워드를 추출할 문자열

    Returns:
        str: 추출된 키워드 (만약 키워드가 없으면 None을 반환)
    """
    match = re.search(r'\[(.*?)\]', toot_body)
    return match.group(1) if match else None

class Listener(StreamListener):
    """
    Mastodon 스트리밍 API의 이벤트를 받아 처리합니다.
    """
    def on_notification(self, notification):
        """
        Mastodon 스트리밍 알림 이벤트 핸들러입니다. 언급 메시지를 처리하고 조사를 진행합니다.

        Parameters:
            notification (dict): Mastodon 알림 정보를 담은 딕셔너리
        """
        if notification['type'] == 'mention':
            got = cleanhtml(notification['status']['content'])
            keyword = getkey(got)

            # [] 미포함된 툿은 무시합니다(조사 선택지에 이어 대화하기 금지...)
            if keyword is None:
                return
            
            try:
                # 조사 시트에서 키워드를 찾는다
                look = search.find(keyword, in_column=1, case_sensitive=True).row
                result = search.get(f"R{look}C2:R{look}C5", value_render_option="UNFORMATTED_VALUE")[0]

                # 정산 요청 감지시(기본 문구를 %정산%으로 입력)
                if result[0] == "%정산%":
                    print(f"유저 {notification['status']['account']['acct']}의 정산 요청 감지")
                    letters = 0
                    URL = f"{BASE}/api/v1/accounts/{notification['status']['account']['id']}/statuses"
                    bf_last = None

                    while True:
                        params = {
                            'limit': 40
                        }

                        fetched = requests.get(URL, params=params,timeout=60)
                        fetched = json.loads(fetched.text)

                        if len(fetched) == 0:
                            break

                        for i in fetched:
                            i = gettext(i['content'])
                            letters += len(i)

                        try:
                            last = fetched[-1]
                            max_id = last['id']
                            last = last['created_at']

                            if bf_last is None:
                                bf_last = last

                            else:
                                if bf_last <= last:
                                    print('끝에 도달했습니다')
                                    break
                        except IndexError:
                            print('끝에 도달했습니다')
                            break
                        params['max_id'] = max_id
                    
                    m.status_post(f"@{notification['status']['account']['acct']} 활동이 정산되었습니다. 현재까지 작성한 글자수는 공미포 {letters}자입니다.", in_reply_to_id=notification['status']['id'], visibility=default_visibility)
                else:
                    # 조사 선택지인 경우
                    if result[1] is True:
                        try:
                            print(f"유저 {notification['status']['account']['acct']} 조건조사 진행 - {notification['status']['id']}")
                            if result[2] is True:
                                # 방문한후 지문이 입력되어 있다면 사용, 없다면 방문여부 무관 기존 지문을 재사용한다.
                                if len(result) > 3:
                                    m.status_post(f"@{notification['status']['account']['acct']} {result[3]}", in_reply_to_id=notification['status']['id'], visibility=default_visibility)
                                else:
                                    m.status_post(f"@{admin_handle} [체크 필요] 키워드 {keyword}의 방문된 후의 지문이 누락되었습니다. 조사전후 차이가 불필요한 경우 \"조사 유무 확인?\" 부분 체크를 해제해주세요.", visibility='private')
                                    m.status_post(f"@{notification['status']['account']['acct']} {result[0]}", in_reply_to_id=notification['status']['id'], visibility=default_visibility)
                                return
                            else:
                                m.status_post(f"@{notification['status']['account']['acct']} {result[0]}", in_reply_to_id=notification['status']['id'], visibility=default_visibility)
                                search.update_cell(look, 4, 'TRUE')
                        except Exception as exception_obj:
                            m.status_post(f"@notice@occm.cc 봇 아이디 {bot['username']}의 체크 관련 오류 발생: {exception_obj}", visibility='private')
                    # 이외(항시 가능)
                    else:
                        print(f"유저 {notification['status']['account']['acct']} 상시조사 진행 - {notification['status']['id']}")
                        m.status_post(f"@{notification['status']['account']['acct']} {result[0]}", in_reply_to_id=notification['status']['id'], visibility=default_visibility)
                        # HACK : 시트상 변화가 없다면 랜덤문구가 안나오기에 시트에 영향이 없는 체크박스를 체크했다 해제한다
                        search.update_cell(look, 4, 'TRUE')
                        search.update_cell(look, 4, 'FALSE')
            except AttributeError:
                m.status_post(f"@{notification['status']['account']['acct']} [{keyword}]{Josa.get_josa(keyword, '은')} {os.getenv('MESSAGE_INVALID_KEYWORD')}", in_reply_to_id=notification['status']['id'], visibility=default_visibility)
                if tag_admin:
                    m.status_post(f"@{admin_handle} {os.getenv('MESSAGE_ADM_INVALID_KEYWORD_PRE')} {keyword}{Josa.get_josa(keyword, '이가')} {os.getenv('MESSAGE_ADM_INVALID_KEYWORD_AFR')}", visibility='private')

def main():
    """
    메인 함수로, Mastodon 스트리밍을 시작합니다.
    """
    m.stream_user(Listener())

if __name__ == '__main__':
    main()
