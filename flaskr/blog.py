from flask import Blueprint, g, redirect, render_template, request, url_for, make_response, jsonify

from .auth import login_required
from .db import get_db
import json

bp = Blueprint('blog', __name__)

@bp.route('/')
def home():
    return redirect(url_for('blog.about'))  # Chuyển hướng về trang About

@bp.route('/tasks')
@login_required
def index():
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Số task mỗi trang
    offset = (page - 1) * per_page
    
    # Lấy các task chưa hoàn thành
    todos = db.execute(
        'SELECT * FROM todo WHERE user_id = ? AND completed = 0 ORDER BY id DESC LIMIT ? OFFSET ?',
        (g.user['id'], per_page, offset)
    ).fetchall()
    
    # Lấy tổng số task chưa hoàn thành
    total_todos = db.execute(
        'SELECT COUNT(*) FROM todo WHERE user_id = ? AND completed = 0',
        (g.user['id'],)
    ).fetchone()[0]
    total_pages = (total_todos + per_page - 1) // per_page
    
    # Lấy danh sách công việc đã hoàn thành
    completed_todos = db.execute(
        'SELECT * FROM todo WHERE user_id = ? AND completed = 1 ORDER BY id DESC',
        (g.user['id'],)
    ).fetchall()
    
    response = make_response(render_template('blog/index.html', todos=todos, completed_todos=completed_todos, page=page, total_pages=total_pages))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        if not title:
            return render_template('blog/create.html', error='Tiêu đề không được để trống.')
        db = get_db()
        db.execute(
            'INSERT INTO todo (user_id, title) VALUES (?, ?)',
            (g.user['id'], title)
        )
        db.commit()
        return redirect(url_for('blog.index'))
    return render_template('blog/create.html')

@bp.route('/update/<int:id>', methods=('GET', 'POST'))
@login_required
def update(id):
    db = get_db()
    todo = db.execute('SELECT * FROM todo WHERE id = ? AND user_id = ?', (id, g.user['id'])).fetchone()

    if todo is None:
        return redirect(url_for('blog.index'))

    if request.method == 'POST':
        title = request.form['title']
        db.execute(
            'UPDATE todo SET title = ? WHERE id = ?',
            (title, id)
        )
        db.commit()
        return redirect(url_for('blog.index'))

    return render_template('blog/update.html', todo=todo)

@bp.route('/update_completed/<int:id>', methods=['POST'])
@login_required
def update_completed(id):
    db = get_db()
    todo = db.execute(
        'SELECT * FROM todo WHERE id = ? AND user_id = ?',
        (id, g.user['id'])
    ).fetchone()

    if todo is None:
        return jsonify({"error": "Không tìm thấy công việc"}), 404

    data = request.get_json()
    if not data or 'completed' not in data:
        return jsonify({"error": "Dữ liệu không hợp lệ"}), 400

    completed = 1 if data['completed'] else 0

    db.execute(
        'UPDATE todo SET completed = ? WHERE id = ?',
        (completed, id)
    )
    db.commit()

    return jsonify({"message": "Cập nhật thành công", "completed": completed, "title": todo['title']})

@bp.route('/delete/<int:id>', methods=('POST',))
@login_required
def delete(id):
    db = get_db()
    db.execute('DELETE FROM todo WHERE id = ? AND user_id = ?', (id, g.user['id']))
    db.commit()
    return redirect(url_for('blog.index'))

@bp.route('/delete_multiple', methods=['POST'])
@login_required
def delete_multiple():
    db = get_db()
    data = request.get_json()
    task_ids = data.get('task_ids', [])
    
    try:
        if task_ids == "all":  # Xóa tất cả task của người dùng
            db.execute('DELETE FROM todo WHERE user_id = ?', (g.user['id'],))
            db.commit()
            return '', 200
        elif not task_ids:  # Không có task nào được chọn
            return 'Không có task nào được chọn', 400
        else:  # Xóa các task được chọn
            task_ids = [int(id) for id in task_ids]
            placeholders = ','.join('?' * len(task_ids))
            db.execute(
                f'DELETE FROM todo WHERE id IN ({placeholders}) AND user_id = ?',
                task_ids + [g.user['id']]
            )
            db.commit()
            return '', 200
    except Exception as e:
        db.rollback()
        return f'Lỗi: {str(e)}', 500

@bp.route('/auto_add_tasks', methods=['POST'])
@login_required
def auto_add_tasks():
    db = get_db()
    try:
        # Đếm số task hiện tại của người dùng
        current_count = db.execute(
            'SELECT COUNT(*) FROM todo WHERE user_id = ?', (g.user['id'],)
        ).fetchone()[0]
        
        # Tính số bắt đầu và số kết thúc cho 10 task tiếp theo
        start = current_count + 1
        end = start + 9  # Thêm 10 task
        
        # Tạo 10 task mới
        for i in range(start, end + 1):
            title = f"Công việc mẫu {i}"
            db.execute(
                'INSERT INTO todo (user_id, title, completed) VALUES (?, ?, 0)',
                (g.user['id'], title)
            )
        db.commit()
        return '', 200
    except Exception as e:
        db.rollback()
        return f'Lỗi: {str(e)}', 500

@bp.route('/about')
def about():
    return render_template('/blog/about.html')