#!/usr/bin/python3
# -*- coding: utf-8 -*-
import re
import os
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

creds = service_account.Credentials.from_service_account_file(os.getenv('GOOGLE_KEYFILE'))
creds = creds.with_scopes(scope)
gc = gspread.authorize(creds)
sh = gc.open_by_url(os.getenv('SHEET_URL'))
search = sh.worksheet(os.getenv('MAIN_SHEET_NAME'))
default_visibility = os.getenv('MASTODON_DEFAULT_VISIBILITY')

BASE = os.getenv('MASTODON_BASE')

m = Mastodon(
    client_id=os.getenv('MASTODON_CLIENT_ID'),
    client_secret=os.getenv('MASTODON_CLIENT_SECRET'),
    access_token=os.getenv('MASTODON_ACCESS_TOKEN'),
    api_base_url=BASE
)

print('성공적으로 로그인 되었습니다.')

CLEANR = re.compile('<.*?>')

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
    def on_notification(self, notification):
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

                # 조사 선택지인 경우
                if result[1] is True:
                    try:
                        if result[2] is True:
                            # 방문한후 지문이 입력되어 있다면 사용, 없다면 방문여부 무관 기존 지문을 재사용한다.
                            if len(result) > 4:
                                m.status_post(f"@{notification['status']['account']['acct']} {result[3]}", in_reply_to_id= notification['status']['id'], visibility=default_visibility)
                            else:
                                print(f'방문된 후의 지문이 별도로 기입되어 있지 않습니다. 해당 키워드의 조사 후 지문을 기입해주세요: {keyword}')
                                m.status_post(f"@{notification['status']['account']['acct']} {result[0]}", in_reply_to_id= notification['status']['id'], visibility=default_visibility)
                            return
                        else:
                            m.status_post(f"@{notification['status']['account']['acct']} {result[0]}", in_reply_to_id= notification['status']['id'], visibility=default_visibility)
                            search.update_cell(look, 4, 'TRUE')
                    except Exception as e:
                        print(f'체크 관련 오류 발생: {e}')
                # 이외(항시 가능)
                else:
                    m.status_post(f"@{notification['status']['account']['acct']} {result[0]}", in_reply_to_id= notification['status']['id'], visibility=default_visibility)
                    # HACK : 시트상 변화가 없다면 랜덤문구가 안나오기에 시트에 영향이 없는 체크박스를 체크했다 해제한다
                    search.update_cell(look, 4, 'TRUE')
                    search.update_cell(look, 4, 'FALSE')
            except AttributeError:
                m.status_post(f"@{notification['status']['account']['acct']} [{keyword}]{Josa.get_josa(keyword, '은')} {os.getenv('MESSAGE_INVALID_KEYWORD')}", in_reply_to_id=result, visibility='unlisted')

def main():
    """
    메인 함수로, Mastodon 스트리밍을 시작합니다.
    """
    m.stream_user(Listener())

if __name__ == '__main__':
    main()
