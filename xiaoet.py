from requests import Session
from m3u8 import loads
import os
from m3u8.model import SegmentList, Segment, find_key


class XET(object):
    APPID = ''  # APPid
    XIAOEID = ''  # Cookie XIAOEID
    RESOURCEID = ''  # ResourceID，这里的resourceid代表课程id
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
            'data[page_size]': '1000',
            'data[order_by]': 'start_at:desc',
            'data[resource_id]': self.RESOURCEID,
            'data[state]': '0'
        }
        # 获取当前课程的信息
        self.header['Referer'] = 'https://pc-shop.xiaoe-tech.com/{appid}/'.format(appid=self.APPID)
        resp = self.session.post(url, data=body, headers=self.header, cookies=self.cookie)
        if resp.status_code != 200:
            raise Exception('获取课程列表失败')
        try:
            # 拼接课程id、标题以及资源类型
            data = [{'id': lesson['id'], 'name': lesson['title'], 'resource_type': lesson['resource_type']} for lesson
                    in resp.json()['data']]
        except Exception as e:
            print("获取课程列表失败")
            exit(1)
        # 返回课程列表
        return data

    def get_lesson_hls(self, resource):
        '''
        :param resource: 这里的resource代表当前课程下的某节课的id
        :return:
        '''
        resource_type = {'2': 'audio.detail.get', '3': 'video.detail.get'}
        url = 'https://pc-shop.xiaoe-tech.com/{appid}/open/{resource}/1.0'.format(appid=self.APPID,
                                                                                  resource=resource_type[
                                                                                      str(resource['resource_type'])])
        body = {
            'data[resource_id]': resource['id']
        }
        self.header['Referer'] = 'https://pc-shop.xiaoe-tech.com/{appid}/video_details?id={resourceid}'.format(
            appid=self.APPID, resourceid=self.RESOURCEID)
        resp = self.session.post(url, data=body, headers=self.header, cookies=self.cookie)
        if resp.status_code != 200:
            raise Exception('获取课程信息失败')
        # 返回当前课程的信息
        hls = resp.json()['data']
        return hls

    def video(self, url, media_dir, title, playurl):
        '''
        :param url: hls 视频流文件
        :param media_dir: 下载保存目录
        :param title:  视频标题
        :param playurl: ts文件地址
        :return:
        '''
        resp = self.session.get(url, headers=self.header)

        media = loads(resp.text)
        # 拼接ts文件列表
        playlist = ["{playurl}{uri}".format(playurl=playurl, uri=uri) for uri in media.segments.uri]

        n = 0
        new_segments = []
        # get ts file list
        for url in playlist:
            ts_file = os.path.join(media_dir, title, 'm_{num}.ts'.format(num=n))
            ts_path = os.path.join(title, 'm_{num}.ts'.format(num=n))
            media.data['segments'][n]['uri'] = ts_path
            new_segments.append(media.data.get('segments')[n])
            # 下载ts文件
            resp = self.session.get(url, headers=self.header, cookies=self.cookie)
            if resp.status_code != 200:
                print('Error: {title} {tsfile}'.format(title=title, tsfile=ts_file))

            # 如果文件不存在或者本地文件大小于接口返回大小不一致则保存ts文件
            if not os.path.exists(ts_file) or os.stat(ts_file).st_size != resp.headers['content-length']:
                with open(ts_file, 'wb') as ts:
                    ts.write(resp.content)

            n += 1

        # change m3u8 data
        media.data['segments'] = new_segments
        # 修改m3u8文件信息
        segments = SegmentList(
            [Segment(base_uri=None, keyobject=find_key(segment.get('key', {}), media.keys), **segment)
             for segment in
             media.data.get('segments', [])])
        media.segments = segments

        # save m3u8 file
        m3u8_file = os.path.join(media_dir, '{title}.m3u8'.format(title=title))
        if not os.path.exists(m3u8_file):
            with open(m3u8_file, 'wb', encoding='utf8') as f:
                f.write(media.dumps())

    def audio(self, url, media_dir, title):
        # 下载音频
        resp = self.session.get(url, headers=self.header, stream=True)
        if resp.status_code != 200:
            print('Error: {title}'.format(title=title))
        else:
            audio_file = os.path.join(media_dir, title, '{title}.mp3'.format(title=title))
            if not os.path.exists(audio_file):
                with open(audio_file, 'wb') as f:
                    f.write(resp.content)

    def download(self):
        # 设置保存目录
        media_dir = 'media'
        # 获取课程信息
        for resourceid in self.get_lesson_list():
            # 课程类型为1和6的直接跳过
            if resourceid['resource_type'] == 1 or resourceid['resource_type'] == 6:
                continue

            data = self.get_lesson_hls(resourceid)
            title = data['title']
            # 判断media目录是否存在
            if not os.path.exists(media_dir):
                os.mkdir(media_dir)
            # 课程类型为2则代表音频，可直接下载
            if resourceid['resource_type'] == 2:
                playurl = data['audio_url']

                if not os.path.exists(os.path.join(media_dir, title)):
                    try:
                        os.mkdir(os.path.join(media_dir, title))
                    except OSError as e:
                        title = title.replace('|', '丨')
                        os.mkdir(os.path.join(media_dir, title))
                self.audio(playurl, media_dir, title)

            # 课程类型为3则代表视频下载后需要手动拼接
            elif resourceid['resource_type'] == 3:
                url = data['video_hls']
                playurl = url.split('v.f230')[0]

                # mkdir media directory
                if not os.path.exists(os.path.join(media_dir, title)):
                    os.mkdir(os.path.join(media_dir, title))

                self.video(url, media_dir, title, playurl)


if __name__ == '__main__':
    XET().download()
