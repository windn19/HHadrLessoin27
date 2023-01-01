import os

from dotenv import load_dotenv
from django.shortcuts import render
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views.generic.base import ContextMixin
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from requests import get

from .forms import ReqForm, UserReqForm, AuthUserReqForm
from .models import Vacancy, Word, Wordskill, Area, Schedule
from hhapp.management.commands.full_db import Command


load_dotenv()
con_dict = {'paginator': None,
            'word': None,
            'skill': None}


def start(request):
    title = 'главная страница'
    return render(request, 'hhapp/index.html', {'title': title})


def form(request):
    title = ''
    if not request.user.is_authenticated:
        form1 = UserReqForm()
    else:
        form1 = AuthUserReqForm(initial={'vacancy': request.user.text,
                                         'areas': request.user.areas.all(),
                                         'schedules': request.user.schedules.all()})
        title = 'страница формы'
    return render(request, 'hhapp/form.html', context={'form': form1, 'title': title})


def result(request):
    print('gist')
    global con_dict
    if request.method == 'POST':
        print('post')
        form = UserReqForm(request.POST)
        if form.is_valid():
            vac = form.cleaned_data['vacancy']
            where = form.cleaned_data['where']
            pages = form.cleaned_data['pages']
            # print(request.POST.getlist('areas'), request.POST.getlist('schedules'))
            areas = [Area.objects.filter(id=it).first() for it in request.POST.getlist('areas')]
            schedules = [Schedule.objects.filter(id=it).first() for it in request.POST.getlist('schedules')]
            # print(areas, schedules, sep='\n')
            com = Command(vac, pages, where, areas, schedules)
            com.handle()
            v = Word.objects.get(word=vac)
            s = Wordskill.objects.filter(id_word_id=v.id).select_related('id_word',
                                                                         'id_skill').order_by('-percent').all()
            vac = Vacancy.active_objects.filter(word_id=v,
                                                area__in=areas,
                                                schedule__in=schedules).select_related('area',
                                                                                       'schedule',
                                                                                       'employer',
                                                                                       'word_id').order_by('published').all()
            print(vac, v, s, sep='\n')
            paginator = Paginator(vac, 5)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)
            con_dict = {'paginator': paginator,
                        'word': v,
                        'skill': s}
            return render(request, 'hhapp/about.html', context={'word': v,
                                                                'skills': s,
                                                                'page_obj': page_obj})

        else:
            form1 = UserReqForm()
            return render(request, 'hhapp/form.html', context={'form': form1})
    else:
        page_number = request.GET.get('page')
        print('get', page_number)
        if page_number:
            paginator = con_dict['paginator']
            page_obj = paginator.get_page(page_number)
            return render(request, 'hhapp/about.html', context={'word': con_dict['word'],
                                                                'skills': con_dict['skill'],
                                                                'page_obj': page_obj})


class WSList(ListView):
    model = Wordskill
    template_name = 'hhapp/ws_list.html'


class AreaList(ListView):
    model = Area
    template_name = 'hhapp/area_list.html'
    paginate_by = 3

    def get_queryset(self):
        return Area.objects.order_by('name').all()


class AreaDetail(DetailView):
    model = Area
    template_name = 'hhapp/area_detail.html'


class AreaPostMixin(ContextMixin):
    def prepare_area(self, url, areas):
        for item in areas:
            # print(item)
            if item['areas'] is not None:
                url[item['name']] = item['id']
                # print(1)
                self.prepare_area(url, item['areas'])
            else:
                url[item['name']] = item['id']

    def parce(self, area):
        r = {'url': 'https://api.superjob.ru/2.0/vacancies/',
             'param': {'town': area,
                       'period': 1},
             'header': {'X-Api-App-Id': os.getenv('key_super'),
                        'Authorization': 'Bearer r.000000010000001.example.access_token',
                        'Content-Type': 'application/x-www-form-urlencoded'}
             }
        self.hh, self.zarpl = dict(), dict()
        for url, d in (('https://api.hh.ru/areas', self.hh), ('https://api.zarplata.ru/areas', self.zarpl)):
            res = get(url).json()
            self.prepare_area(d, res)
        res = get(r['url'], headers=r['header'], params=r['param']).json()
        return {'name': area, 'ind_hh': self.hh.get(area, 0),
                'ind_zarp': self.zarpl.get(area, 0),
                'ind_super': res['objects'][0]['town']['id'] if res['objects'] else 0}

    def post(self, request, *args, **kwargs):
        text = request.POST['name']
        print(text)
        new_index = self.parce(text)
        print(new_index)
        Area.objects.create(**new_index)
        return render(request, 'hhapp/area_list.html', context={'object_list': Area.objects.order_by('name').all()})


class AreaCreate(LoginRequiredMixin, CreateView, AreaPostMixin):
    model = Area
    fields = ['name']
    success_url = reverse_lazy('hh:area_list')
    template_name = 'hhapp/area_create.html'


class AreaUpdateView(UpdateView):
    model = Area
    fields = ['name']
    success_url = reverse_lazy('hhapp:area_list')
    template_name = 'hhapp/area_create.html'


class AreaDeleteView(DeleteView):
    model = Area
    success_url = reverse_lazy('hhapp:area_list')
    template_name = 'hhapp/area_delete_confirm.html'



