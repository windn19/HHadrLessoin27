from collections import Counter
from datetime import datetime
import os
from pprint import pprint
import re
from threading import Thread
from queue import Queue

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from dotenv import load_dotenv
from pycbrf import ExchangeRates
from requests import get


from hhapp.models import Word, Wordskill, Skill, Vacancy, Schedule, Employer, Area, Type

load_dotenv()
alias = {'на дому': {'sup': 2,
                     'hh': 'remote'},
         'на территории работодателя': {'sup': 0,
                                        'hh': 'fullDay'},
         'разъездного характера': {'sup': 0,
                                   'hh': '4'},
         'полный день': {'sup': 0,
                         'hh': 'fullDay'},
         'сменный график': {'sup': 0,
                            'hh': 'shift'},
         'гибкий график': {'sup': 0,
                           'hh': 'flexible'},
         'удаленная работа': {'sup': 2,
                              'hh': 'remote'},
         'удалённая работа (на дому)': {'sup': 2,
                                        'hh': 'remote'},
         'не имеет значения': {'sup': 0,
                               'hh': 'fullDay'},
         'вахтовый метод': {'sup': 0,
                            'hh': 'flyInFlyOut'}}
cache = {'area': {},
         'employer': {},
         'schedule': {},
         'type': {},
         'word': {},
         'vac': {obj.published for obj in Vacancy.active_objects.all()}}


def req_page(urls, head, p, i, place, q: Queue):
    p['size'] = i
    req = get(urls, params=p, headers=head).json()
    # print(q.qsize())
    for it in req[place]:
        q.put(it)


class Command(BaseCommand):
    def __init__(self, vacancy, pages, where, areas, schedules):
        super().__init__()
        self.vac = vacancy
        self.pages = pages
        self.where = where
        self.areas = areas
        self.schedules = schedules

    def handle(self, *args, **options):
        res = start(self.vac, pages=self.pages, where=self.where, areas=self.areas, schedules=self.schedules)
        print(res)
        add_words(res)
        add_skills(res)
        add_ws(res)


def skills1(pp: str, skil: list, skillis: list):
    skills = set()
    pp_re = re.findall(r'\s[A-Za-z-?]+', pp)
    its = set(x.strip(' -').lower() for x in pp_re)
    for sk in skil:
        skillis.append(sk['name'].lower())
        skills.add(sk['name'].lower())
    for it in its:
        if not any(it in x for x in skills):
            skillis.append(it)
    return skillis


def parce_sup(vacancy, areas, schedules, pages='3', where='all'):
    url = 'https://api.superjob.ru/2.0/vacancies/'
    key = os.getenv('key_super')
    sal = {'from': [], 'to': [], 'cur': []}
    q = Queue()
    print('super', vacancy, areas, schedules)
    for schedule in schedules:
        for area in areas:
            print(11)
            head = {
                'X-Api-App-Id': key,
                'Authorization': 'Bearer r.000000010000001.example.access_token',
                'Content-Type': 'application/x-www-form-urlencoded'}

            p = {'keyword': vacancy,
                 'town': area.name,
                 'place_of_work': alias[schedule.name]['sup'],
                 'period': 3}

            res = get(url, headers=head, params=p).json()
            # pprint(res)
            count = len(res['objects'])
            ski = []
            if count:
                pages1 = res['total'] // count
                print(pages, pages1)
                result = {
                    'keywords': 'python',
                    'count': count}
                pages1 = min(pages1, int(pages))
                ths = [Thread(target=req_page, args=(url, head, p, i, 'objects', q)) for i in range(pages1)]
                for th in ths:
                    th.start()

                for th in ths:
                    th.join()

                    # urls, head, p, i, place, q: Queue
                print(q.qsize())
                result['count'] = q.qsize()
                for _ in range(result['count']):
                    vac = q.get()
                    url1 = vac['link']
                    area_id = vac['town']['id']
                    area_name = vac['town']['title']
                    employer_id = vac['client'].get('id', 0)
                    employer_name = vac['client'].get('title', '')
                    employer_link = vac['client'].get('client_logo', None)
                    title = vac['profession']
                    published = datetime.fromtimestamp(vac['date_published'])
                    schedule = vac['place_of_work']['title'].lower()
                    type = 'Открытая'
                    snippet = vac['vacancyRichText']
                    if area_name not in cache['area'].keys():
                        cache['area'][area_name] = Area.objects.filter(name=area_name).first()
                    if employer_id not in cache['employer'].keys():
                        cache['employer'][employer_id] = Employer.objects.filter(name=employer_name,
                                                                                 ind=employer_id,
                                                                                 link=employer_link).first()
                    if schedule not in cache['schedule'].keys():
                        cache['schedule'][schedule] = Schedule.objects.filter(name=schedule).first()
                    if type not in cache['type'].keys():
                        cache['type'][type] = Type.objects.filter(name=type).first()
                    if vacancy not in cache['word'].keys():
                        cache['word'][vacancy] = Word.objects.filter(word=vacancy).first()
                    # are = Area.objects.filter(name=area_name).first()
                    are = cache['area'][area_name]
                    if are:
                        if are.ind_super == 0:
                            are.ind_super = area_id
                            are.save()
                    else:
                        are = Area.objects.create(name=area_name, ind_super=area_id)
                        cache['area'][area_name] = are

                    em = cache['employer'][employer_id]
                    if not em:
                        em = Employer.objects.create(name=employer_name, ind=employer_id, link=employer_link)
                        cache['employer'][employer_id] = em

                    sc = cache['schedule'][schedule]
                    if not sc:
                        sc = Schedule.objects.create(name=schedule)
                        cache['schedule'][schedule] = sc

                    t = cache['type'][type]
                    if not t:
                        t = Type.objects.create(name=type)
                        cache['type'][type] = t

                    w = cache['word'][vacancy]
                    if not w:
                        w = Word.objects.create(word=vacancy, count=1, up=1, down=1)
                        cache['word'][vacancy] = w
                    ski = skills1(snippet, [], ski)
                    print(vac['payment_from'], vac['payment_to'], sep='\n')
                    if vac['payment_from'] or vac['payment_to']:
                        salary_from = vac['payment_from'] if vac['payment_from'] else vac['payment_to']
                        salary_to = vac['payment_to'] if vac['payment_to'] else vac['payment_from']
                        sal['from'].append(salary_from)
                        sal['to'].append(salary_to)
                    else:
                        salary_from, salary_to = 0, 0
                    print(published, cache['vac'], sep='\n')
                    print(published in cache['vac'])
                    # pub1 = datetime.strptime(published, '%Y-%m-%d %H:%M:%S.%f')
                    if published not in cache['vac']:
                        Vacancy.objects.create(published=published, name=title, url=url1, word_id=w, area=are,
                                               schedule=sc, snippet=snippet, salaryFrom=salary_from,
                                               salaryTo=salary_to, employer=em, type=t)
            else:
                print('отмена региона')

    # print(sal, ski)
    if not ski:
        return None
    sk2 = Counter(ski)
    up = sum(sal['from']) / len(sal['from'])
    down = sum(sal['to']) / len(sal['to'])
    result.update({'down': round(up, 2),
                   'up': round(down, 2)})
    add = []
    for name, count in sk2.most_common(5):
        add.append({'name': name,
                    'count': count,
                    'percent': round((count / result['count']) * 100, 2)})
    result['requirements'] = add
    return result


def parce(url, vacancy, areas, schedules, pages='3', where='all'):
    # url = 'https://api.hh.ru/vacancies'
    areas = [area.ind_hh if url.startswith('https://api.h') else area.ind_zarp for area in areas]
    schedules = [alias[schedule.name]['hh'] for schedule in schedules]
    rate = ExchangeRates()
    vacancy = vacancy if where == 'all' else f'NAME: {vacancy}' if where == 'name' else f'COMPANY_NAME: {vacancy}'
    q = Queue()
    p = {'text': vacancy,
         'area': areas,
         'schedule': schedules,
         'period': 3}
    r = get(url=url, params=p).json()
    count_pages = r['pages']
    all_count = len(r['items'])
    result = {
        'keywords': vacancy,
        'count': all_count}
    sal = {'from': [], 'to': [], 'cur': []}
    skillis = []
    count_pages = min(count_pages, int(pages))
    ths = [Thread(target=req_page, args=(url, {}, p, i, 'items', q)) for i in range(count_pages)]
    for th in ths:
        th.start()

    for th in ths:
        th.join()

    result['count'] = q.qsize()
    for _ in range(q.qsize()):
        res = q.get()
        # pprint(res)
        skills = set()
        url1 = res['alternate_url']
        area_id = res['area']['id']
        area_name = res['area']['name']
        employer_id = res['employer'].get('id', 0)
        employer_name = res['employer']['name']
        employer_link = res['employer']['logo_urls']['original'] if res['employer'].get('logo_urls', 0) else None
        title = res['name']
        published = res['published_at']
        schedule = res['schedule']['name'].lower()
        type = res['type']['name']
        if area_name not in cache['area'].keys():
            cache['area'][area_name] = Area.objects.filter(name=area_name).first()
        if employer_id not in cache['employer'].keys():
            cache['employer'][employer_id] = Employer.objects.filter(name=employer_name,
                                                                     ind=employer_id,
                                                                     link=employer_link).first()
        if schedule not in cache['schedule'].keys():
            cache['schedule'][schedule] = Schedule.objects.filter(name=schedule).first()
        if type not in cache['type'].keys():
            cache['type'][type] = Type.objects.filter(name=type).first()
        if vacancy not in cache['word'].keys():
            # cache['count'] += 1
            cache['word'][vacancy] = Word.objects.filter(word=vacancy).first()
        are = cache['area'][area_name]
        if url.startswith('https://api.hh'):
            if are:
                if not are.ind_hh:
                    are.ind_hh = area_id
                    are.save()
            else:
                are = Area.objects.create(name=area_name, ind_hh=area_id)
                cache['area'][area_name] = are
        else:
            if are:
                if not are.ind_zarp:
                    are.ind_zarp = area_id
                    are.save()
            else:
                are = Area.objects.create(name=area_name, ind_zarp=area_id)
                cache['area'][area_name] = are
        em = cache['employer'][employer_id]
        if not em:
            em = Employer.objects.create(name=employer_name, ind=employer_id, link=employer_link)
            cache['employer'][employer_id] = em

        sc = cache['schedule'][schedule]
        if not sc:
            sc = Schedule.objects.create(name=schedule)
            cache['schedule'][schedule] = sc

        t = cache['type'][type]
        if not t:
            t = Type.objects.create(name=type)
            cache['type'][type] = t

        w = cache['word'][vacancy]
        if not w:
            w = Word.objects.create(word=vacancy, count=1, up=1, down=1)
            cache['word'][vacancy] = w
        ar = res['area']
        res_full = get(res['url']).json()
        pp = res_full['description']
        pp_re = re.findall(r'\s[A-Za-z-?]+', pp)
        its = set(x.strip(' -').lower() for x in pp_re)
        for sk in res_full['key_skills']:
            skillis.append(sk['name'].lower())
            skills.add(sk['name'].lower())
        for it in its:
            if not any(it in x for x in skills):
                skillis.append(it)
        if res_full['salary']:
            code = res_full['salary']['currency']
            if rate[code] is None:
                code = 'RUR'
            k = 1 if code == 'RUR' else float(rate[code].value)
            salary_from = k * res_full['salary']['from'] if res['salary']['from'] else k * res_full['salary']['to']
            salary_to = k * res_full['salary']['to'] if res['salary']['to'] else k * res_full['salary']['from']
            sal['from'].append(salary_from)
            sal['to'].append(salary_to)
        else:
            salary_from, salary_to = 0, 0
        snippet = res_full['description']

        if published not in cache['vac']:
            Vacancy.objects.create(published=published, name=title, url=url1, word_id=w, area=are, schedule=sc,
                                   snippet=snippet, salaryFrom=salary_from, salaryTo=salary_to, employer=em,
                                   type=t)
    sk2 = Counter(skillis)
    try:
        up = sum(sal['from']) / len(sal['from'])
        down = sum(sal['to']) / len(sal['to'])
        result.update({'down': round(up, 2),
                       'up': round(down, 2)})
    except ZeroDivisionError:
        return None
    add = []
    for name, count in sk2.most_common(5):
        add.append({'name': name,
                    'count': count,
                    'percent': round((count / result['count']) * 100, 2)})
    result['requirements'] = add
    return result


def start(vacancy, areas, schedules, pages='3', where='all'):
    sk1 = parce_sup(vacancy, pages=pages, where=where, areas=areas, schedules=schedules)
    print(sk1)
    sk2 = parce(url='https://api.hh.ru/vacancies', vacancy=vacancy, pages=pages,
                where=where, areas=areas, schedules=schedules)
    sk3 = parce(url='https://api.zarplata.ru/vacancies', vacancy=vacancy, pages=pages,
                where=where, areas=areas, schedules=schedules)
    result = {'keywords': vacancy}
    res = (it for it in (sk1, sk2, sk3) if it)
    sk = {}
    for item in res:
        result['count'] = result.get('count', 0) + item['count']
        result['down'] = item['down'] if not result.get('down', None) else (result['down'] + item['down']) / 2
        result['up'] = item['up'] if not result.get('up', None) else (result['up'] + item['up']) / 2
        for it in item['requirements']:
            if sk.get(it['name'], {}):
                sk[it['name']] = {'count': sk[it['name']]['count'] + it['count'],
                                  'percent': round((sk[it['name']]['percent'] + it['percent']) / 2, 2)}
            else:
                sk[it['name']] = {'count': it['count'],
                                  'percent': it['percent']}
    # print(sk)
    result['requirements'] = sorted([{'name': it,
                                      'count': sk[it]['count'],
                                      'percent': sk[it]['percent']} for it in sk.keys() if it],
                                    key=lambda x: x['percent'],
                                    reverse=True)
    return result


def add_words(res):
    if not res['requirements']:
        print('Not edit')
        return
    try:
        obj = Word.objects.get(word=res['keywords'])
        print(obj)
        if obj.count < res['count']:
            obj.count = res['count']
            obj.up = res['up']
            obj.down = res['down']
            obj.save()
            print('Edit')
        else:
            print('Not edit')
    except ObjectDoesNotExist:
        Word.objects.create(word=res['keywords'], count=res['count'], up=res['up'], down=res['down'])


def add_skills(res):
    if not res['requirements']:
        print('Not edit')
        return
    for item in res['requirements']:
        try:
            r = Skill.objects.get(name=item['name'])
            print('skill not added')
        except ObjectDoesNotExist:
            Skill.objects.create(name=item['name'])


def add_ws(res):
    if not res['requirements']:
        print('Not edit')
        return
    word = Word.objects.get(word=res['keywords'])
    for item in res['requirements']:
        skill = Skill.objects.get(name=item['name'])
        print(word, skill)
        r = Wordskill.objects.filter(id_word=word, id_skill=skill).select_related('id_word', 'id_skill').first()
        if not r:
            Wordskill.objects.create(id_word=word, id_skill=skill, count=item['count'], percent=item['percent'])
            print('ws done')
        elif word.count < res['count']:
            r.count = item['count']
            r.percent = item['percent']
            print('ws edit')
        else:
            print('ws not edit')


if __name__ == '__main__':
    parce('python', pages='0')
