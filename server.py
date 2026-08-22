# -*- coding: utf-8 -*-
# TBTOOL KEY SERVER - Dành riêng cho tool Canh Code
# Cơ chế: Key VIP, 1 device duy nhất, khóa được từ admin

import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify

# ==================== CONFIG ====================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tbtool_secret_key_2026")

DATA_FILE = "keys.json"
SALT = "TbToolKeySalt2026"
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "token_admin_2026")

# ==================== DỮ LIỆU ====================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"keys": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"keys": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==================== HÀM HỖ TRỢ ====================
def generate_key():
    return f"TBTOOL_VIP_{secrets.token_hex(4).upper()}"

def get_device_hash(device_id: str) -> str:
    return hashlib.sha256(f"{device_id}:{SALT}".encode()).hexdigest()[:32]

# ==================== API ENDPOINTS ====================
@app.route('/')
def index():
    return "TBTOOL Key Server Running - OK"

@app.route('/api/admin/create_key', methods=['POST'])
def admin_create_key():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({"success": False, "message": "Missing token"}), 401
    token = auth.replace('Bearer ', '')
    if token != ADMIN_TOKEN:
        return jsonify({"success": False, "message": "Invalid token"}), 403

    data = request.get_json() or {}
    duration_hours = data.get("duration_hours", 720)
    note = data.get("note", "")

    key = generate_key()
    all_data = load_data()
    key_record = {
        "key": key,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "duration_hours": duration_hours,
        "device_id": None,
        "device_hash": None,
        "activated_at": None,
        "expiry_time": None,
        "is_activated": False,
        "is_locked": False,
        "note": note
    }
    all_data["keys"].append(key_record)
    save_data(all_data)
    return jsonify({"success": True, "key": key, "duration_hours": duration_hours})

@app.route('/api/admin/list_keys', methods=['GET'])
def admin_list_keys():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({"success": False, "message": "Missing token"}), 401
    token = auth.replace('Bearer ', '')
    if token != ADMIN_TOKEN:
        return jsonify({"success": False, "message": "Invalid token"}), 403

    all_data = load_data()
    keys_info = []
    for k in all_data["keys"]:
        keys_info.append({
            "key": k["key"],
            "created_at": k["created_at"],
            "duration_hours": k["duration_hours"],
            "is_activated": k["is_activated"],
            "device_id": k["device_id"],
            "activated_at": k["activated_at"],
            "expiry_time": k["expiry_time"],
            "is_locked": k["is_locked"],
            "note": k["note"]
        })
    return jsonify({"success": True, "keys": keys_info})

@app.route('/api/admin/lock_key', methods=['POST'])
def admin_lock_key():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({"success": False, "message": "Missing token"}), 401
    token = auth.replace('Bearer ', '')
    if token != ADMIN_TOKEN:
        return jsonify({"success": False, "message": "Invalid token"}), 403

    data = request.get_json() or {}
    key = data.get("key", "")
    all_data = load_data()
    for k in all_data["keys"]:
        if k["key"] == key:
            k["is_locked"] = True
            save_data(all_data)
            return jsonify({"success": True, "message": f"Key {key} đã bị khóa"})
    return jsonify({"success": False, "message": "Không tìm thấy key"}), 404

@app.route('/api/admin/unlock_key', methods=['POST'])
def admin_unlock_key():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({"success": False, "message": "Missing token"}), 401
    token = auth.replace('Bearer ', '')
    if token != ADMIN_TOKEN:
        return jsonify({"success": False, "message": "Invalid token"}), 403

    data = request.get_json() or {}
    key = data.get("key", "")
    all_data = load_data()
    for k in all_data["keys"]:
        if k["key"] == key:
            k["is_locked"] = False
            save_data(all_data)
            return jsonify({"success": True, "message": f"Key {key} đã mở khóa"})
    return jsonify({"success": False, "message": "Không tìm thấy key"}), 404

@app.route('/api/verify_key', methods=['POST'])
def verify_key():
    data = request.get_json() or {}
    device_id = data.get("device_id", "")
    key = data.get("key", "").strip().upper()
    if not device_id or not key:
        return jsonify({"success": False, "message": "Thiếu thông tin"}), 400

    all_data = load_data()
    key_record = None
    for k in all_data["keys"]:
        if k["key"] == key:
            key_record = k
            break

    if not key_record:
        return jsonify({"success": False, "message": "Key không tồn tại"}), 404

    if key_record["is_locked"]:
        return jsonify({"success": False, "message": "Key đã bị khóa"}), 403

    if key_record["is_activated"]:
        if key_record["device_hash"] != get_device_hash(device_id):
            return jsonify({"success": False, "message": "Key đã dùng trên thiết bị khác"}), 403
        if key_record["expiry_time"]:
            expiry = datetime.fromisoformat(key_record["expiry_time"])
            if datetime.now(timezone.utc) > expiry:
                return jsonify({"success": False, "message": "Key đã hết hạn"}), 403
        return jsonify({
            "success": True,
            "duration_hours": key_record["duration_hours"],
            "key_type": "VIP",
            "is_forever": key_record["duration_hours"] >= 87600
        })

    key_record["is_activated"] = True
    key_record["device_id"] = device_id
    key_record["device_hash"] = get_device_hash(device_id)
    key_record["activated_at"] = datetime.now(timezone.utc).isoformat()
    key_record["expiry_time"] = (datetime.now(timezone.utc) + timedelta(hours=key_record["duration_hours"])).isoformat()
    save_data(all_data)
    return jsonify({
        "success": True,
        "duration_hours": key_record["duration_hours"],
        "key_type": "VIP",
        "is_forever": key_record["duration_hours"] >= 87600
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
