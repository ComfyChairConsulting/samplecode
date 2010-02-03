
"""
This is from an internal project tracking application; it includes 
logic for reassigning tickets and sending email notifications, as well 
as defining priorities and relations between this and a related app 
which tracks clients.
"""

from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

from django.core.mail import send_mail

from django.forms import ModelForm

from django.contrib.sites.models import Site
from django.contrib.sites.managers import CurrentSiteManager

from clients.models import Client


STATUS_CODES = (
    (1, 'Open'),
    (2, 'In Progress'),
    (3, 'Closed'),
    )

PRIORITY_CODES = (
    (1, 'Suggestion'),
    (2, 'Improvement'),
    (3, 'Normal'),
    (4, 'Important'),
    (5, 'Critical'),
    )

apps = [app for app in settings.INSTALLED_APPS if not app.startswith('django.')]


class Project(models.Model):
    name    = models.CharField(max_length=255)
    notes    = models.TextField()
    
    client    = models.ForeignKey(Client)
    
    user    = models.ForeignKey(User, blank=True, null=True)
    
    site    = models.ForeignKey(Site)
    objects    = models.Manager()
    on_site    = CurrentSiteManager()
    
    def __unicode__(self):
        return self.name
    
    def getOpenTickets(self):
        return Ticket.objects.filter(project=self)
    
    def get_absolute_url(self):
        return "/projects/" + str(self.id)


class ProjectForm(ModelForm):
    class Meta:
        model    = Project
        fields    = ( 'client', 'name', 'notes' )


class Ticket(models.Model):
    title        = models.CharField(max_length=100)
    description    = models.TextField(blank=True)
    
    submitted_date    = models.DateField(auto_now_add=True)
    modified_date    = models.DateField(auto_now=True)
    
    status        = models.IntegerField(default=1, choices=STATUS_CODES)
    priority    = models.IntegerField(default=1, choices=PRIORITY_CODES)
    
    project        = models.ForeignKey(Project)
    submitter    = models.ForeignKey(User, related_name="submitter")
    
    assignee        = models.ForeignKey(User, related_name="assignee", blank=True, null=True)
    old_assignee    = models.ForeignKey(User, related_name="old_assignee", blank=True, null=True)
    
    site    = models.ForeignKey(Site)
    objects    = models.Manager()
    on_site    = CurrentSiteManager()
    
    class Admin:
        list_display = ('title', 'status', 'priority', 'submitter', 
            'submitted_date', 'modified_date')
        list_filter = ('priority', 'status', 'submitted_date')
        search_fields = ('title', 'description',)

    class Meta:
        ordering = ('status', 'priority', 'submitted_date', 'title')

    def __unicode__(self):
        return self.title
    
    def get_absolute_url(self):
        return '/projects/tickets/' + str(self.id)
    
    def save(self):
        if not self.id:
            super(Ticket, self).save()
            
            if self.assignee:
                # send creation email to assignee if exists
                send_mail(
                    "A new ticket has been assigned to you", 
                    "View it here:\nhttp://" + Site.objects.get_current().domain + self.get_absolute_url(), 
                    "noreply@boothboss.com", 
                    [self.assignee.email], 
                    fail_silently=False
                    )
        elif self.old_assignee and self.assignee and (self.old_assignee != self.assignee):
            # send email to new assignee
            send_mail(
                "A ticket has been assigned to you", 
                "View it here:\nhttp://" + Site.objects.get_current().domain + self.get_absolute_url(), 
                "noreply@boothboss.com", 
                [self.assignee.email], 
                fail_silently=False
                )
        elif self.assignee:
            # send update email to assignee
            send_mail(
                "A ticket assigned to you has been updated", 
                "View it here:\nhttp://" + Site.objects.get_current().domain + self.get_absolute_url(), 
                "noreply@boothboss.com", 
                [self.assignee.email], 
                fail_silently=False
                )
        
        self.old_assignee = self.assignee
        
        super(Ticket, self).save()
        

class TicketForm(ModelForm):
    class Meta:
        model    = Ticket
        fields    = ( 'title', 'description', 'status', 'priority', 'project', 'assignee' )


"""
This is from a gallery site; it handles user-submitted gallery data and 
includes a class built to post to an arbitrary number of twitter 
accounts.  It includes duplicate checking based on actual page data, 
custom-generated thumbnail information and URL.
"""

from django.db import models
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify
from django.core.files import File

from tagging.models import Tag
import os, twitter, time, unicodedata
from PIL import Image

from settings import THUMBNAIL_SIZE, MEDIA_ROOT, MEDIA_URL, GALLERY_ROOT


TWITTER_FEEDS = {
    'Account 1': { 'username': 'twittername1', 'password': 'twitterpass1', },
    'Account 2': { 'username': 'twittername2', 'password': 'twitterpass2', },
    }


class TwitterUpdate(models.Model):
    feed = models.CharField(max_length=63)
    content = models.CharField(max_length=255)
    
    def save(self):
        try:
            self.content = unicodedata.normalize('NFKD', self.content).encode('latin-1','ignore')
        except:
            pass
        
        super(TwitterUpdate, self).save()
    
    def post(self):
        if self.feed not in TWITTER_FEEDS:
            print "Tried to post to invalid feed: " + self.feed
            print "Object ID: " + self.id
            return
        
        feed = TWITTER_FEEDS[self.feed]
        
        try:
            self.content = unicodedata.normalize('NFKD', self.content).encode('latin-1','ignore')
            
            api = twitter.Api(feed['username'], feed['password'])
            status = api.PostUpdate(self.content)
            
            if status.text == self.content:
                self.delete()
            else:
                raise Exception, "Update not applied; presumably need to wait and try again: " + time.strftime('%m/%d/%y %H:%M:%S')
        except Exception, e:
            print "Error posting to Twitter for user " + feed['username']
            print "Attempted to post:", self.content
            print "Exception:", e


class Gallery(models.Model):
    name = models.CharField(max_length=63)
    description = models.TextField(null=True, blank=True)
    keywords = models.CharField(max_length=255, null=True, blank=True)
    sitename = models.CharField(max_length=63)
    link = models.URLField()
    rating = models.DecimalField(decimal_places=1, max_digits=2, null=True, blank=True)
    
    hash_value = models.CharField(max_length=63, null=True, blank=True)
    
    date = models.DateTimeField(auto_now_add=True)
    
    thumbnail_url = models.CharField(max_length=255, null=True, blank=True)
    
    slug = models.SlugField(max_length=127, null=True, blank=True)
    
    tags = models.ManyToManyField(Tag)
    
    def generateThumbnailPath(instance, filename):
        return os.path.join(MEDIA_ROOT, GALLERY_ROOT, filename)
    
    def generateThumbnailURL(self, filename):
        return os.path.join(MEDIA_URL, GALLERY_ROOT, filename)
    
    def preview_images(self):
        images = self.galleryimage_set.all()
        
        count = len(images)
        
        previews = []
        
        if count > 0:
            previews.append(images[0])
            
            if count >= 4:
                previews.append(images[((count / 4) * 2) - 1])
                previews.append(images[((count / 4) * 3) - 1])
            elif count == 3:
                previews.append(images[1])
            
            if count > 1:
                previews.append(images[count - 1])
        
        return previews
    
    def __unicode__(self):
        return self.name
    
    def get_absolute_url(self):
        return "/galleries/" + self.slug
    
    def save(self):
        if len(self.name) > 63:
            self.name = self.name[:62]
        if len(self.sitename) > 63:
            self.sitename = self.sitename[:62]
        
        if not self.slug:
            self.slug = slugify(self.name)
            
            for gallery in Gallery.objects.filter(slug__exact=self.slug):
                if gallery.id != self.id:
                    if not self.id:
                        super(Gallery, self).save()
                    
                    self.slug += "-" + str(self.id)
        
        super(Gallery, self).save()


class RemovedGallery(models.Model):
    link    = models.URLField()
    
    def __unicode__(self):
        return self.link


class GalleryImage(models.Model):
    def generateImagePath(instance, filename):
        return os.path.join(MEDIA_ROOT, GALLERY_ROOT, instance.gallery.slug, filename)
    
    def generateThumbnailPath(instance, filename):
        return os.path.join(MEDIA_ROOT, GALLERY_ROOT, instance.gallery.slug, "thumbnails", filename)
    
    def generateImageURL(instance, filename):
        return os.path.join(MEDIA_URL, GALLERY_ROOT, instance.gallery.slug, "thumbnails", filename)
    
    def generateThumbnailURL(instance, filename):
        return os.path.join(MEDIA_URL, GALLERY_ROOT, instance.gallery.slug, "thumbnails", filename)
    
    image = models.ImageField(upload_to=generateImagePath, null=True, blank=True)
    image_url = models.CharField(max_length=511, null=True, blank=True)
    thumbnail_url = models.CharField(max_length=511, null=True, blank=True)
    
    gallery = models.ForeignKey(Gallery)
    
    def url(self):
        url = MEDIA_URL[:-1] + self.image.url.replace(os.path.join(MEDIA_ROOT), '')
        return url
    
    def __unicode__(self):
        return self.image.name
    
    def save(self):
        super(GalleryImage, self).save()
        
        if self.image:
            filename = self.image.path
            image = Image.open(filename)
            thumbnail = Image.new("RGBA", THUMBNAIL_SIZE, (235,215,185))
            thumbnail_path = GalleryImage.generateThumbnailPath(self, str(self.id) + ".jpg")
            
            thumbnail_resize = ( THUMBNAIL_SIZE[0] - 8, THUMBNAIL_SIZE[1] - 8 )
            
            image.thumbnail(thumbnail_resize, Image.ANTIALIAS)
            (x, y) = image.size
            (a, b) = ( (THUMBNAIL_SIZE[0] - x) / 2, (THUMBNAIL_SIZE[1] - y) / 2 )
            thumbnail.paste(image, (a, b, x + a, y + b))
            
            thumbnail.save(thumbnail_path, "JPEG", quality=90)
            
            self.thumbnail_url = GalleryImage.generateThumbnailURL(self, str(self.id) + ".jpg")
            self.image_url = self.url()
            
            super(GalleryImage, self).save()


class Rating(models.Model):
    user = models.ForeignKey(User)
    gallery = models.ForeignKey(Gallery, related_name="user_rating")
    
    value = models.DecimalField(decimal_places=1, max_digits=2)
    
    def __init__(self, user, gallery, value):
        self.user = user
        self.gallery = gallery
        self.value = value
