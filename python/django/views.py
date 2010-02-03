
"""
This is from an internal project tracking application; it extends two 
generic views as well as defining logic for various sorting operations.
"""

from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext, loader
from models import Project, Ticket, STATUS_CODES, PRIORITY_CODES

from django.contrib.auth.models import User

from django.views.generic.list_detail import object_list, object_detail


def ticket_detail(request, object_id, queryset):
    instance = queryset.get(id=object_id)
    
    for status in STATUS_CODES:
        if instance.status == status[0]:
            status = status[1]
            break
    
    for priority in PRIORITY_CODES:
        if instance.priority == priority[0]:
            priority = priority[1]
            break
    
    extra_context = {
        'status': status,
        'priority': priority,
        }
    
    return object_detail(
        request,
        object_id=object_id,
        queryset=queryset,
        extra_context=extra_context
        )


def ticket_list(request):
    try:
        status = request.GET['status']
    except:
        status = 'Open'
    
    try:
        user = User.objects.get(username=request.GET['user'])
    except:
        user = None
    
    try:
        project = Project.objects.get(name=request.GET['project'])
    except:
        project = None
    
    users = User.objects.all()
    projects = Project.on_site.all()
    
    extra_context = {
            'status_codes': [ pair[1] for pair in STATUS_CODES ],
            'current_status': status,
            
            'users': users,
            'current_user': user,
            
            'projects': projects,
            'current_project': project,
            }
    
    for code in STATUS_CODES:
        if status == code[1]:
            status = code[0]
    
    try:
        status = int(status)
    except:
        status = 1
    
    queryset = Ticket.on_site.filter(status=status)
    
    if user:
        queryset = queryset.filter(assignee=user)
    
    return object_list(request, queryset=queryset, extra_context=extra_context)


def index(request):
    projects = Project.objects.on_site()
    
    tmpl = loader.get_template('base.html')
    
    context = RequestContext(request, {
        'projects': projects,
        })
    
    return HttpResponse(tmpl.render(context))


"""
This view retrieves a list of objects based on an arbitrary number of 
user-specified tags, extending a generic list view to take advantage 
of automatic pagination.  It also handles user specification for tag 
cloud view modes.
"""

from django.views.generic.list_detail import object_list
from django.template import RequestContext

from settings import PAGINATE_BY

from tagging.models import Tag


def tag_object_list(request, cls, tag_string='', template_name='tag_object_list.html'):
    tags = []
    
    rss = False
    
    for tag_name in tag_string.split('/'):
        try:
            tag = Tag.objects.get(name__iexact=tag_name.strip())
            
            tags.append(tag)
        except Tag.DoesNotExist:
            if tag_name == 'rss':
                rss = True
            
            continue
    
    items = cls.objects.all()
    
    for tag in tags:
        items = items.filter(tags__id=tag.id)
    
    items = items.order_by('-id')
    
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    
    try:
        mode = request.GET['view_mode']
        
        if mode == 'all':
            request.session["view_mode"] = 'all'
        else:
            request.session["view_mode"] = ''
    except:
        pass
    
    try:
        if request.session["view_mode"] == 'all':
            mode = 'all'
        else:
            mode = ''
    except:
        request.session["view_mode"] = ''
        mode = ''
    
    if mode == 'all':
        display_tags = Tag.getSubsetTags(cls, tags, limit=False)
    else:
        display_tags = Tag.getSubsetTags(cls, tags)
    
    extra_context = {
        'display_tags': display_tags,
        'viewing_tags': tags,
        'view_mode': mode,
        }
    
    if rss is True:
        template_name = 'tag_object_list_rss.html'
        
        if len(items):
            extra_context['last_build'] = items[0].date
        else:
            extra_context['last_build'] = 0
    
    return object_list(request, items, extra_context=extra_context, template_name=template_name, page=page, paginate_by=PAGINATE_BY)
