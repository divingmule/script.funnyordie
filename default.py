import re
import urllib
import urllib2
import xbmcgui
import xbmcaddon
import StorageServer
from traceback import format_exc
from BeautifulSoup import BeautifulSoup

addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')
addon_version = addon.getAddonInfo('version')
addon_path = xbmc.translatePath(addon.getAddonInfo('path'))
cache = StorageServer.StorageServer("funnyordie", 2)
base_url = 'http://www.funnyordie.com'
cache.dbg = True


def addon_log(string):
    xbmc.log("[%s-%s]: %s" %(addon_id, addon_version, string))


## Thanks to Fredrik Lundh for this function - http://effbot.org/zone/re-sub.htm#unescape-html
def unescape(text):
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text # leave as is
    return re.sub("&#?\w+;", fixup, text)


def make_request(url, data=None, headers=None):
    addon_log('Request URL: %s' %url)
    if headers is None:
        headers = {'User-agent' : 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:22.0) Gecko/20100101 Firefox/22.0',
                   'Referer' : base_url}
    try:
        req = urllib2.Request(url, data, headers)
        response = urllib2.urlopen(req)
        data = response.read()
        # addon_log(str(response.info()))
        redirect_url = response.geturl()
        response.close()
        if redirect_url != url:
            addon_log('Redirect URL: %s' %redirect_url)
        return data
    except urllib2.URLError, e:
        addon_log('We failed to open "%s".' %url)
        if hasattr(e, 'reason'):
            addon_log('We failed to reach a server.')
            addon_log('Reason: %s' %e.reason)
        if hasattr(e, 'code'):
            addon_log('We failed with error code - %s.' %e.code)


def play(listitem, playlist=False):
    if playlist:
        playlist = xbmc.PlayList(1)
        playlist.clear()
        for i in listitem:
            url = 'http://vo.fod4.com/v/%s/v600.mp4' %(i.getProperty('href').split('/')[2])
            playlist.add(url, i)
        player.play(playlist)
    else:
        try:
            url = 'http://vo.fod4.com/v/%s/v600.mp4' %(listitem.getProperty('href').split('/')[2])
            player.play(url, listitem)
        except:
            addon_log('Exception play: %s' %format_exc())


def get_videos(soup):
    videos = []
    video_items = [i for i in soup.findAll('article') if i.has_key('class') and 'video' in i['class']]
    for i in video_items:
        exclusive = False
        if 'exclusive' in i['class']:
            exclusive = True
        videos.append({'title': i.a['title'], 'href': i.a['href'], 'thumb': i.img['src'], 'exclusive': exclusive})
    return videos


def get_videos_nav(soup):
    items = [
        soup.find('div', attrs={'class': 'browse_navigation'})('div', attrs={'id': 'date_filter'})[0],
        soup.find('div', attrs={'class': 'browse_navigation'})('div', attrs={'id': 'sort_filter'})[0],
        soup.find('div', attrs={'class': 'browse_navigation'})('div', attrs={'id': 'category_filter'})[0]]
    nav = {'current': []}
    for i in items:
        nav['current'].append([{'label': x.string, 'value': y.string} for x in i('span')[0] for y in i('span')[1].a][0])
        nav[i['id']] = [{'title': x.string, 'href': x['href']} for x in i('a')]
    return nav


def get_homepage(url):
    addon_log('get_homepage')
    data = make_request(url)
    soup = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
    videos = get_videos(soup)
    next_page = base_url + soup.find('a', attrs={'class': "infinite-more-link js-infinite-more-link"})['href']
    if url == base_url:
        jumbo = []
        jumbo_items = soup.find('div', attrs={'id': "jumbotron-slideshow"})('section')
        for i in jumbo_items:
            href = i.a['href']
            if '/videos/' in href:
                title = i.h2.string
                if i.h3.string:
                    title += ': ' + i.h3.string
                if title and '&#' in title:
                    title = unescape(title)
                jumbo.append({'title': title, 'href': href, 'thumb': i.img['src']})
        cat_items = soup.find('section', attrs={'id': 'browse-menu-featured'})('article')
        celeb_items = soup.find('section', attrs={'id': 'browse-menu-celebrities'})('article')
        link_items = soup.find('ul', attrs={'class': 'quick-links'})('a')
        page_dict = {
            'page': next_page,
            'jumbo': jumbo,
            'videos': videos,
            'links': [{'title': i.string, 'href': i['href']} for i in link_items],
            'celebs': [{'href': i.a['href'], 'thumb': i.img['data-src'], 'title': i.a.div.string} for i in celeb_items],
            'categories': [{'href': i.a['href'], 'thumb': i.img['data-src'], 'title': i.a.div.string}
                           for i in cat_items if not i.a.div.string == 'Articles' and not i.a.div.string == 'Images']
            }
        cache.set('homepage', repr(page_dict))
        return page_dict
    else:
        return {'page': next_page, 'videos': videos}


def get_page(href):
    addon_log('get page: %s' %href)
    data = make_request(base_url + href)
    soup = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
    return get_videos(soup)


def get_search():
    keyboard = xbmc.Keyboard('', 'Search')
    keyboard.doModal()
    if keyboard.isConfirmed() == False:
        return
    search_query = keyboard.getText()
    if len(search_query) == 0:
        return
    addon_log('get_search: %s' %search_query)
    href = '/search/a?search_term=%s' %urllib.quote_plus(search_query)
    data = make_request(base_url + href)
    soup = BeautifulSoup(data, convertEntities=BeautifulSoup.HTML_ENTITIES)
    try:
        next_page = soup.find('nav', attrs={'class': "pagination"}).find('a', attrs={'rel': 'next'})['href']
    except:
        next_page = None
    return (next_page, get_videos(soup))


def get_listitem(item, is_video=False):
    thumb = ''
    if item.has_key('thumb'):
        thumb = item['thumb']
    listitem = xbmcgui.ListItem('[B]%s[/B]' %item['title'], thumbnailImage=thumb)
    if is_video:
        listitem.setInfo(type="Video", infoLabels={"Title": item['title']})
        if item.has_key('exclusive') and item['exclusive']:
            listitem.setProperty('exclusive', 'true')
    listitem.setProperty('href', item['href'])
    return listitem



class FunnyOrDieGUI(xbmcgui.WindowXMLDialog):
    def __init__( self, *args, **kwargs ):
        xbmcgui.WindowXMLDialog.__init__(self)
        self.action_previous_menu = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)
        self.menu_settings = ['BrowseMenu', 'HomeMenu', 'VideosMenu',
                              'Videos', 'ContextDialog', 'FilterDialog']
        self.home_url = base_url
        self.menu = None
        self.video_page = None

    def onInit(self):
        self.window = xbmcgui.Window(xbmcgui.getCurrentWindowDialogId())
        self.jumbo_control = self.window.getControl(1271)
        self.videos_control = self.window.getControl(1272)
        self.load_more_button = self.window.getControl(1274)
        self.cat_control = self.window.getControl(1281)
        self.celeb_control = self.window.getControl(1282)
        self.nav_button_1 = self.window.getControl(1261)
        self.nav_button_2 = self.window.getControl(1262)
        self.nav_button_3 = self.window.getControl(1263)
        self.nav_button_4 = self.window.getControl(1264)
        self.video_filter_button_1 = self.window.getControl(1266)
        self.video_filter_button_2 = self.window.getControl(1267)
        self.video_filter_button_3 = self.window.getControl(1268)
        self.context_dialog = self.window.getControl(1285)
        self.context_button_1 = self.window.getControl(1286)
        self.filter_dialog = self.window.getControl(1288)
        self.filter_list = self.window.getControl(1289)
        self.display_homepage()

    def display_homepage(self, page=False):
        data = get_homepage(self.home_url)
        if not page:
            self.jumbo_control.reset()
            self.videos_control.reset()
            for i in data['jumbo']:
                self.jumbo_control.addItem(get_listitem(i, True))
        control_position = self.videos_control.getSelectedPosition()
        for i in data['videos']:
            self.videos_control.addItem(get_listitem(i, True))
        if data['page']:
            self.load_more_button.setEnabled(True)
            self.window.setProperty('nextPage', data['page'])
            addon_log('nextHomePage: %s' %data['page'])
        else:
            self.load_more_button.setEnabled(False)
            self.window.setProperty('nextPage', '')
        if page:
            self.move_videos_control(control_position)
        else:
            self.set_menu('HomeMenu')

    def display_all_videos(self):
        control_position = None
        if self.video_page is None:
            href = '/browse/videos/all/all/most_recent/this_week'
            self.videos_control.reset()
            self.set_menu('VideosMenu')
        else:
            if '&page' in self.video_page:
                control_position = self.videos_control.getSelectedPosition()
            href = self.video_page
        data = self.get_all_videos(href)
        for i in data:
            self.videos_control.addItem(get_listitem(i, True))
        if control_position:
            self.move_videos_control(control_position)

    def move_videos_control(self, control_position):
        self.setFocus(self.videos_control)
        xbmc.executebuiltin("Control.Move(1272, %s)" %control_position)

    def get_all_videos(self, href):
        addon_log('get all videos: %s' %href)
        url = base_url + href
        soup = BeautifulSoup(make_request(url), convertEntities=BeautifulSoup.HTML_ENTITIES)
        try:
            next_page = soup.find('a', attrs={'class': "infinite-more-link js-infinite-more-link"})['href']
            self.video_page = next_page
            addon_log('next_video_page: %s' %next_page)
            self.load_more_button.setEnabled(True)
        except:
            addon_log('Exception next_page: %s' %format_exc())
            next_page = None
            self.load_more_button.setEnabled(False)
        if not '&page' in href:
            self.set_video_nav(get_videos_nav(soup))
        return get_videos(soup)

    def display_browse(self):
        if self.cat_control.size() < 1:
            data = eval(cache.get('homepage'))
            for i in data['categories']:
                self.cat_control.addItem(get_listitem(i))
            for i in data['celebs']:
                self.celeb_control.addItem(get_listitem(i))
        self.set_menu('BrowseMenu')

    def display_page(self, href):
        data = get_page(href)
        self.videos_control.reset()
        for i in data:
            self.videos_control.addItem(get_listitem(i, True))
        self.load_more_button.setEnabled(False)
        self.set_menu('Videos')

    def display_search(self, next_page, items):
        for i in items:
            self.videos_control.addItem(get_listitem(i, True))
        if next_page:
            self.video_page = next_page
            self.load_more_button.setEnabled(True)
        else:
            self.load_more_button.setEnabled(False)
        self.set_menu('Videos')

    def set_menu(self, menu=None):
        self.menu = None
        self.video_page = None
        for i in self.menu_settings:
            xbmc.executebuiltin("Skin.Reset(%s)" %i)
        if menu:
            xbmc.executebuiltin("Skin.ToggleSetting(%s)" %menu)
            self.menu = menu
            self.set_nav_control()

    def set_nav_control(self):
        self.nav_button_1.setLabel('[B]Browse[/B]')
        self.nav_button_2.setLabel('[B]All Videos[/B]')
        if self.menu == 'HomeMenu':
            v_control = self.jumbo_control
        elif self.menu == 'BrowseMenu':
            v_control = self.cat_control
            self.nav_button_1.setLabel('[B]Home[/B]')
        elif self.menu == 'Videos':
            v_control = self.videos_control
        elif self.menu == 'VideosMenu':
            self.nav_button_2.setLabel('[B]Home[/B]')
            v_control = self.video_filter_button_1
        self.nav_button_1.setNavigation(v_control, v_control, self.nav_button_4, self.nav_button_2)
        self.nav_button_2.setNavigation(v_control, v_control, self.nav_button_1, self.nav_button_3)
        self.nav_button_3.setNavigation(v_control, v_control, self.nav_button_2, self.nav_button_4)
        self.nav_button_4.setNavigation(v_control, v_control, self.nav_button_3, self.nav_button_1)
        xbmc.sleep(300)
        self.setFocus(v_control)

    def set_video_nav(self, nav):
        for i in nav['current']:
            if i['label'] == 'VIEWING':
                control = self.window.getControl(1266)
            elif i['label'] == 'SORT BY':
                control = self.window.getControl(1267)
            elif i['label'] == 'DATE':
                control = self.window.getControl(1268)
            control.setLabel('%s :  [B]%s[/B]' %(i['label'], i['value']))
        cache.set('videos_nav', repr(nav))

    def set_video_filter_button(self, reset=False):
        for i in [self.video_filter_button_1, self.video_filter_button_2, self.video_filter_button_3]:
            if not reset:
                i.controlDown(self.filter_dialog)
                i.controlUp(self.filter_dialog)
            else:
                i.controlDown(self.videos_control)
                i.controlUp(self.nav_button_1)

    def filter_videos(self, filter_type):
        items = eval(cache.get('videos_nav'))[filter_type]
        for i in items:
            self.filter_list.addItem(get_listitem(i))
        xbmc.executebuiltin("Skin.ToggleSetting(FilterDialog)")

    def set_current_control(self):
        try:
            self.current_control = [i for i in [self.jumbo_control, self.videos_control] if self.getFocus() == i][0]
            addon_log('current control: %s'  %self.current_control.getId())
        except:
            self.current_control = None

    def shutdown(self):
        self.window.setProperty('videos_filter', '')
        self.window.setProperty('nextPage', '')
        self.set_menu()
        self.close()

    def onAction(self, action):
        if xbmc.getCondVisibility("Window.IsVisible(fullscreenvideo)") == True:
            if action == 13:
                player.stop()
            elif xbmc.getCondVisibility("Window.IsVisible(videoosd)") == False:
                xbmc.executebuiltin("ActivateWindow(videoosd)")

        elif action == 117:
            # context menu
            self.set_current_control()
            if self.current_control:
                xbmc.executebuiltin("Skin.ToggleSetting(ContextDialog)")
                self.setFocus(self.context_button_1)

        elif action == 13:
            #keyboard x key
            self.shutdown()

        elif action in self.action_previous_menu:
            addon_log('Action: action_previous_menu')
            if self.menu == 'FilterDialog':
                self.set_menu('VideosMenu')
                self.setFocus(self.videos_control)
            elif not self.menu == 'HomeMenu':
                self.display_homepage()
            else:
                self.shutdown()

    def onClick(self, control_id):
        addon_log('onClick control_id: %s' %control_id)

        # navigation controls
        if control_id == 1261:
            if self.menu == 'BrowseMenu':
                self.home_url = base_url
                self.videos_control.reset()
                self.display_homepage()
            else:
                self.display_browse()

        elif control_id == 1262:
            if self.menu == 'VideosMenu':
                self.home_url = base_url
                self.videos_control.reset()
                self.display_homepage()
            else:
                self.video_page = None
                self.videos_control.reset()
                self.display_all_videos()

        elif control_id == 1263:
            search = get_search()
            if search:
                self.videos_control.reset()
                self.display_search(*search)

        elif control_id == 1264:
            # exit
            self.shutdown()

        # video filter controls
        elif control_id == 1266:
            self.menu = 'FilterDialog'
            if self.window.getProperty('videos_filter') == 'category_filter':
                xbmc.executebuiltin("Skin.ToggleSetting(FilterDialog)")
            else:
                self.filter_list.reset()
                self.window.setProperty('videos_filter', 'category_filter')
                self.filter_dialog.setPosition(95, 85)
                self.filter_videos('category_filter')
                xbmc.sleep(500)
            self.set_video_filter_button()
            self.setFocus(self.filter_list)


        elif control_id == 1267:
            self.menu = 'FilterDialog'
            if self.window.getProperty('videos_filter') == 'sort_filter':
                xbmc.executebuiltin("Skin.ToggleSetting(FilterDialog)")
            else:
                self.filter_list.reset()
                self.window.setProperty('videos_filter', 'sort_filter')
                self.filter_dialog.setPosition(435, 85)
                self.filter_videos('sort_filter')
                xbmc.sleep(500)
            self.set_video_filter_button()
            self.setFocus(self.filter_list)


        elif control_id == 1268:
            self.menu = 'FilterDialog'
            if self.window.getProperty('videos_filter') == 'date_filter':
                xbmc.executebuiltin("Skin.ToggleSetting(FilterDialog)")
            else:
                self.filter_list.reset()
                self.window.setProperty('videos_filter', 'date_filter')
                self.filter_dialog.setPosition(780, 85)
                self.filter_videos('date_filter')
                xbmc.sleep(500)
            self.set_video_filter_button()
            self.setFocus(self.filter_list)

        # home page controls
        elif control_id == 1271:
            item = self.jumbo_control.getSelectedItem()
            play(item)

        elif control_id == 1272:
            item = self.videos_control.getSelectedItem()
            play(item)

        elif control_id == 1274:
            if self.menu == 'HomeMenu':
                self.home_url = self.window.getProperty('nextPage')
                self.display_homepage(True)
            elif self.menu == 'VideosMenu':
                self.display_all_videos()

        # browse controls
        elif control_id == 1281:
            item = self.cat_control.getSelectedItem()
            self.display_page(item.getProperty('href'))

        elif control_id == 1282:
            item = self.celeb_control.getSelectedItem()
            self.display_page(item.getProperty('href'))

        # context dialog controls
        elif control_id == 1286:
            xbmc.executebuiltin("Skin.Reset(ContextDialog)")
            items = [self.current_control.getListItem(i)
                for i in range(self.current_control.getSelectedPosition(), self.current_control.size())]
            play(items, True)
            self.current_control = None

        elif control_id == 1287:
            xbmc.executebuiltin("Skin.Reset(ContextDialog)")
            self.setFocus(self.current_control)

        # videos filter control
        elif control_id == 1289:
            xbmc.executebuiltin("Skin.Reset(FilterDialog)")
            item = self.filter_list.getSelectedItem()
            self.video_page = item.getProperty('href')
            self.set_video_filter_button(True)
            self.videos_control.reset()
            self.display_all_videos()
            self.menu = 'VideosMenu'
            self.setFocus(self.videos_control)


if (__name__ == "__main__"):
    addon_log('script starting')
    player = xbmc.Player()
    window = FunnyOrDieGUI('script-funnyordie.xml', addon_path)
    window.doModal()

addon_log('script finished')