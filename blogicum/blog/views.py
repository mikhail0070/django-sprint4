from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView

from .forms import CommentForm, PostForm, ProfileForm, RegistrationForm
from .models import Category, Comment, Post

User = get_user_model()
POSTS_PER_PAGE = 10


def get_published_posts():
    return (
        Post.objects.filter(
            is_published=True,
            category__is_published=True,
            pub_date__lte=timezone.now(),
        )
        .select_related("author", "location", "category")
        .annotate(comment_count=Count("comments", distinct=True))
        .order_by("-pub_date")
    )


def paginate_queryset(request, queryset):
    return Paginator(queryset, POSTS_PER_PAGE).get_page(request.GET.get("page"))


def index(request):
    page_obj = paginate_queryset(request, get_published_posts())
    return render(request, "blog/index.html", {"page_obj": page_obj})


def post_detail(request, post_id):
    post = get_object_or_404(Post.objects.select_related(
        "author", "location", "category"
    ), pk=post_id)

    is_author = request.user.is_authenticated and request.user == post.author
    if not is_author and post not in get_published_posts():
        from django.http import Http404
        raise Http404("Публикация не найдена")

    comments = post.comments.select_related("author").all()
    return render(
        request,
        "blog/detail.html",
        {
            "post": post,
            "comments": comments,
            "form": CommentForm(),
        },
    )


def category_posts(request, category_slug):
    category = get_object_or_404(
        Category, slug=category_slug, is_published=True
    )
    posts = (
        category.posts.filter(
            is_published=True,
            pub_date__lte=timezone.now(),
        )
        .select_related("author", "location", "category")
        .annotate(comment_count=Count("comments", distinct=True))
        .order_by("-pub_date")
    )
    return render(
        request,
        "blog/category.html",
        {"category": category, "page_obj": paginate_queryset(request, posts)},
    )


def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    if request.user.is_authenticated and request.user == profile_user:
        posts = profile_user.posts.all()
    else:
        posts = profile_user.posts.filter(
            is_published=True,
            category__is_published=True,
            pub_date__lte=timezone.now(),
        )

    posts = (
        posts.select_related("author", "location", "category")
        .annotate(comment_count=Count("comments", distinct=True))
        .order_by("-pub_date")
    )
    return render(
        request,
        "blog/profile.html",
        {
            "profile": profile_user,
            "page_obj": paginate_queryset(request, posts),
        },
    )


class RegistrationView(CreateView):
    form_class = RegistrationForm
    template_name = "registration/registration_form.html"
    success_url = reverse_lazy("login")


@login_required
def edit_profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect("blog:profile", username=request.user.username)
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "blog/user.html", {"form": form})


@login_required
def create_post(request):
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect("blog:profile", username=request.user.username)
    else:
        form = PostForm()
    return render(request, "blog/create.html", {"form": form})


@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.author != request.user:
        return redirect("blog:post_detail", post_id=post.pk)

    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            return redirect("blog:post_detail", post_id=post.pk)
    else:
        form = PostForm(instance=post)
    return render(request, "blog/create.html", {"form": form})


@login_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.author != request.user:
        return redirect("blog:post_detail", post_id=post.pk)

    form = PostForm(instance=post)
    if request.method == "POST":
        post.delete()
        return redirect("blog:profile", username=request.user.username)
    return render(request, "blog/create.html", {"form": form})


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if request.method != "POST":
        return redirect("blog:post_detail", post_id=post.pk)

    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
    return redirect("blog:post_detail", post_id=post.pk)


@login_required
def edit_comment(request, post_id, comment_id):
    comment = get_object_or_404(
        Comment, pk=comment_id, post_id=post_id
    )
    if comment.author != request.user:
        return redirect("blog:post_detail", post_id=post_id)

    if request.method == "POST":
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            return redirect("blog:post_detail", post_id=post_id)
    else:
        form = CommentForm(instance=comment)
    return render(
        request,
        "blog/comment.html",
        {"form": form, "comment": comment, "post": comment.post},
    )


@login_required
def delete_comment(request, post_id, comment_id):
    comment = get_object_or_404(
        Comment, pk=comment_id, post_id=post_id
    )
    if comment.author != request.user:
        return redirect("blog:post_detail", post_id=post_id)

    if request.method == "POST":
        comment.delete()
        return redirect("blog:post_detail", post_id=post_id)
    return render(
        request,
        "blog/comment.html",
        {"comment": comment, "post": comment.post},
    )