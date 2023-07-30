#!/usr/bin/python3
# -*- coding: utf-8 -*-
from mastodon import Mastodon
from mastodon.streaming import StreamListener
import re
from oauth2client.service_account import ServiceAccountCredentials
import gspread


# 구글시트 세팅


scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file",
         "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_name("api 키 json 파일명(확장명인 .json까지 붙여서)", scope)
gc = gspread.authorize(creds)
sh = gc.open_by_url('시트 url')
search = sh.worksheet("조사")

# 구글시트 세팅 끝

# 마스토돈 계정 세팅

BASE = '자동봇이 지내는 서버의 url'

m = Mastodon(
    client_id="클라이언트 키",
    client_secret="클라이언트 비밀키",
    access_token="액세스 토큰",
    api_base_url=BASE
)

print('성공적으로 로그인 되었습니다.')

# 마스토동 계정 세팅 끝

CLEANR = re.compile('<.*?>')

def cleanhtml(raw_html):
  cleantext = re.sub(CLEANR, '', raw_html)
  return cleantext

class Listener(StreamListener):

    def on_notification(self, notification):
        if notification['type'] == 'mention':
            got = cleanhtml(notification['status']['content'])

            if got.__contains__('[') is False or got.__contains__(']') is False:
                pass

            else:
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
                    m.status_post(f"@{notification['status']['account']['acct']} [{keyword}]는(은) 존재하지 않는 키워드입니다.\n만일 오류라고 판단되는 경우 운영진, 혹은 봇의 관리자에게 연락을 주세요.", in_reply_to_id=result, visibility='unlisted')
    
    def handle_heartbeat(self):
        return super().handle_heartbeat()

def main():
    m.stream_user(Listener())

if __name__ == '__main__':
    main()