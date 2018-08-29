from requests import Session
from m3u8 import loads
import os
from m3u8.model import SegmentList, Segment, find_key


class XET(object):
    APPID = ''  # APPid
    XIAOEID = ''  # Cookie XIAOEID
    RESOURCEID = ''  # ResourceID
    sessionid = ''  # Cookie laravel_session
    session = Session()
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36',
        'Referer': '',
        'Origin': 'http://pc-shop.xiaoe-tech.com',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    cookie = {
        'XIAOEID': XIAOEID,
        'laravel_session': sessionid
    }

    def get_lesson_list(self):
        url = 'https://pc-shop.xiaoe-tech.com/{appid}/open/column.resourcelist.get/2.0'.format(appid=self.APPID)
        body = {
            'data[page_index]': '0',
            'data[page_size]': '100',
            'data[order_by]': 'start_at:desc',
            'data[resource_id]': self.RESOURCEID,
            'data[state]': '0'
        }
        self.header['Referer'] = 'https://pc-shop.xiaoe-tech.com/{appid}/'.format(appid=self.APPID)
        resp = self.session.post(url, data=body, headers=self.header, cookies=self.cookie)
        if resp.status_code != 200:
            raise Exception('获取课程列表失败')
        try:
            data = [{'id': lesson['id'], 'name': lesson['title']} for lesson in resp.json()['data']]
        except Exception as e:
            print("获取课程列表失败")
            exit(1)
        return data

    def get_lesson_hls(self, resourceid):
        url = 'https://pc-shop.xiaoe-tech.com/{appid}/open/video.detail.get/1.0'.format(appid=self.APPID)
        body = {
            'data[resource_id]': resourceid
        }
        self.header['Referer'] = 'https://pc-shop.xiaoe-tech.com/{appid}/video_details?id={resourceid}'.format(
            appid=self.APPID, resourceid=self.RESOURCEID)
        resp = self.session.post(url, data=body, headers=self.header, cookies=self.cookie)
        if resp.status_code != 200:
            raise Exception('获取课程信息失败')
        hls = resp.json()['data']
        return hls

    def download(self):
        media_dir = 'media'
        for resourceid in self.get_lesson_list():
            data = self.get_lesson_hls(resourceid['id'])
            url = data['video_hls']
            title = data['title']
            playurl = url.split('v.f230')[0]

            # mkdir media directory
            if not os.path.exists(media_dir):
                os.mkdir(media_dir)

            if not os.path.exists(os.path.join(media_dir, title)):
                os.mkdir(os.path.join(media_dir, title))

            resp = self.session.get(url, headers=self.header)
            media = loads(resp.text)
            playlist = ["{playurl}{uri}".format(playurl=playurl, uri=uri) for uri in media.segments.uri]

            n = 0
            new_segments = []
            # get ts file list
            for url in playlist:
                ts_file = os.path.join(media_dir, title, 'm_{num}.ts'.format(num=n))
                ts_path = os.path.join(title, 'm_{num}.ts'.format(num=n))
                media.data['segments'][n]['uri'] = ts_path
                new_segments.append(media.data.get('segments')[n])
                if not os.path.exists(ts_file):
                    resp = self.session.get(url, headers=self.header, cookies=self.cookie)
                    if resp.status_code != 200:
                        print('Error: {title} {tsfile}'.format(title=title,tsfile=ts_file))
                    else:
                        with open(ts_file, 'wb') as ts:
                            ts.write(resp.content)
                n += 1

            # change m3u8 data
            media.data['segments'] = new_segments
            segments = SegmentList(
                [Segment(base_uri=None, keyobject=find_key(segment.get('key', {}), media.keys), **segment)
                 for segment in
                 media.data.get('segments', [])])
            media.segments = segments

            # save m3u8 file
            m3u8_file = os.path.join(media_dir, '{title}.m3u8'.format(title=title))
            if not os.path.exists(m3u8_file):
                with open(m3u8_file, 'w', encoding='utf8') as f:
                    f.write(media.dumps())

if __name__ == '__main__':
    XET().download()
