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
scoped_credentials = creds.with_scopes(scope)
gc = gspread.authorize(creds)
sh = gc.open_by_url(os.getenv('SHEET_URL'))
search = sh.worksheet(os.getenv('MAIN_SHEET_NAME'))

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
    cleantext = re.sub(CLEANR, '', raw_html)
    return cleantext

class Listener(StreamListener):
    def on_notification(self, notification):
        if notification['type'] == 'mention':
            got = cleanhtml(notification['status']['content'])

            # [] 미포함 
            if got.__contains__('[') is False and got.__contains__(']') is False:
                pass

            else:
                # TODO : 좀더 깔끔한 방식으로 변경하기
                keyword = got[got.find('[')+1:got.find(']')]
                
                try:
                    look = search.find(keyword, in_column=1, case_sensitive=True).row
                    result = search.get(f"R{look}C2:R{look}C5", value_render_option="UNFORMATTED_VALUE")[0]
                    print(result[1])
                    if result[1] is True:
                        try:
                            if result[2] is True:
                                try:
                                    m.status_post(f"@{notification['status']['account']['acct']} {result[3]}", in_reply_to_id= notification['status']['id'], visibility='private')
                                except:
                                    print(f'방문된 후의 지문이 별도로 기입되어 있지 않습니다. 해당 키워드의 조사 후 지문을 기입해주세요: {keyword}')
                                    m.status_post(f"@{notification['status']['account']['acct']} {result[0]}", in_reply_to_id= notification['status']['id'], visibility='private')
                                return
                            else:
                                m.status_post(f"@{notification['status']['account']['acct']} {result[0]}", in_reply_to_id= notification['status']['id'], visibility='private')
                                search.update_cell(look, 4, 'TRUE')
                        except Exception as e:
                            print(f'체크 관련 오류 발생: {e}')
                    else:
                        m.status_post(f"@{notification['status']['account']['acct']} {result[0]}", in_reply_to_id= notification['status']['id'], visibility='private')
                except AttributeError:
                    m.status_post(f"@{notification['status']['account']['acct']} [{keyword}]{Josa.get_josa(keyword, '은')} {os.getenv('MESSAGE_INVALID_KEYWORD')}", in_reply_to_id=result, visibility='unlisted')

def main():
    m.stream_user(Listener())

if __name__ == '__main__':
    main()
