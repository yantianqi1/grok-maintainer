from __future__ import annotations

from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for


ADMIN_SESSION_KEY = "admin_username"
FILTER_OPTIONS = (
    ("all", "全部"),
    ("enabled", "启用"),
    ("disabled", "停用"),
    ("error", "有错误"),
    ("unused", "未成功调用"),
)


def create_admin_blueprint(store, admin_settings) -> Blueprint:
    blueprint = Blueprint("admin", __name__)
    blueprint.add_app_template_filter(mask_api_key, "mask_api_key")

    @blueprint.get("/admin/login")
    def login_page():
        if _is_logged_in():
            return redirect(url_for("admin.dashboard"))
        return render_template("admin_login.html", username=admin_settings.username)

    @blueprint.post("/admin/login")
    def login_submit():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if store.verify_admin_credentials(username, password):
            session[ADMIN_SESSION_KEY] = username
            return redirect(url_for("admin.dashboard"))
        flash("账号或密码错误", "error")
        return render_template("admin_login.html", username=username), 401

    @blueprint.post("/admin/logout")
    @_login_required
    def logout():
        session.pop(ADMIN_SESSION_KEY, None)
        return redirect(url_for("admin.login_page"))

    @blueprint.get("/admin")
    @_login_required
    def dashboard():
        filter_name = _read_filter_name(request.args.get("filter"))
        return render_template(
            "admin_dashboard.html",
            stats=store.get_dashboard_stats(),
            keys=store.list_api_keys(filter_name),
            filters=FILTER_OPTIONS,
            selected_filter=filter_name,
        )

    @blueprint.post("/admin/keys/bulk-add")
    @_login_required
    def bulk_add_keys():
        result = store.bulk_add_api_keys(request.form.get("bulk_keys", ""))
        flash(f"新增 {result.added_count} 把 key，跳过 {result.skipped_count} 条重复项", "success")
        return _redirect_dashboard(request.form.get("filter"))

    @blueprint.post("/admin/keys/bulk-action")
    @_login_required
    def bulk_action():
        filter_name = _read_filter_name(request.form.get("filter"))
        try:
            key_ids = _read_key_ids(request.form.getlist("key_ids"))
        except ValueError:
            flash("提交的 key 参数不合法", "error")
            return _redirect_dashboard(filter_name)
        if not key_ids:
            flash("请先勾选至少一把 key", "error")
            return _redirect_dashboard(filter_name)
        try:
            affected_count = store.apply_bulk_action(request.form.get("action", ""), key_ids)
        except ValueError as error:
            flash(str(error), "error")
            return _redirect_dashboard(filter_name)
        flash(f"批量操作完成，影响 {affected_count} 把 key", "success")
        return _redirect_dashboard(filter_name)

    @blueprint.post("/admin/keys/<int:key_id>/toggle")
    @_login_required
    def toggle_key(key_id: int):
        store.toggle_api_key(key_id)
        flash("已更新 key 状态", "success")
        return _redirect_dashboard(request.form.get("filter"))

    @blueprint.post("/admin/keys/<int:key_id>/delete")
    @_login_required
    def delete_key(key_id: int):
        store.delete_api_key(key_id)
        flash("已删除 key", "success")
        return _redirect_dashboard(request.form.get("filter"))

    return blueprint


def mask_api_key(api_key: str) -> str:
    value = str(api_key).strip()
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:6]}...{value[-4:]}"


def _is_logged_in() -> bool:
    return bool(session.get(ADMIN_SESSION_KEY))


def _read_filter_name(value: str | None) -> str:
    normalized = str(value or "all").strip().lower()
    valid_values = {item[0] for item in FILTER_OPTIONS}
    return normalized if normalized in valid_values else "all"


def _read_key_ids(values: list[str]) -> tuple[int, ...]:
    normalized_ids = dict.fromkeys(int(value) for value in values if str(value).strip())
    return tuple(normalized_ids)


def _redirect_dashboard(filter_name: str | None):
    return redirect(url_for("admin.dashboard", filter=_read_filter_name(filter_name)))


def _login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if _is_logged_in():
            return view_func(*args, **kwargs)
        return redirect(url_for("admin.login_page"))

    return wrapped
