# -*- coding: utf-8 -*-
"""
SpectroSolHub API client for INTI Partner.
Ported from JSol'Ex Java implementation.

Author: Cédric Champeau / Valérie Desnoux
"""

import requests

DEFAULT_BASE_URL = "https://spectrosolhub.com"
TIMEOUT = 30
USER_AGENT = "INTI_Partner"


class SpectroSolHubException(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code

    def is_totp_required(self):
        return self.status_code == 403


class SpectroSolHubClient:
    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
        })

    @staticmethod
    def login(base_url, username, password, token_name, totp_code=None):
        url = base_url.rstrip("/") + "/api/auth/token"
        body = {
            "username": username,
            "password": password,
            "tokenName": token_name,
        }
        if totp_code:
            body["totpCode"] = totp_code

        try:
            resp = requests.post(
                url,
                json=body,
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            )
        except requests.RequestException as e:
            raise SpectroSolHubException(f"Failed to connect to SpectroSolHub: {e}")

        if resp.status_code == 201:
            return resp.json().get("token")
        raise SpectroSolHubException(resp.text, resp.status_code)

    def fetch_quota(self):
        return self._get("/api/users/me/quota")

    def create_session(self, session_request):
        return self._post("/api/sessions", session_request, expected_status=201)

    def publish_session(self, session_id):
        return self._post(f"/api/sessions/{session_id}/publish", expected_status=200)

    def initiate_upload(self, upload_request):
        return self._post("/api/uploads/initiate", upload_request, expected_status=201)

    def upload_part(self, upload_id, part_number, data):
        url = f"{self.base_url}/api/uploads/{upload_id}/parts/{part_number}"
        try:
            resp = self.session.put(
                url,
                data=data,
                headers={"Content-Type": "application/octet-stream"},
                timeout=TIMEOUT,
            )
        except requests.RequestException as e:
            raise SpectroSolHubException(f"Failed to upload part {part_number}: {e}")

        if resp.status_code != 200:
            raise SpectroSolHubException(
                f"Failed to upload part {part_number}: {resp.text}",
                resp.status_code,
            )

    def complete_upload(self, upload_id):
        return self._post(f"/api/uploads/{upload_id}/complete", expected_status=201)

    def upload_image(self, session_id, title, image_kind, image_metadata_json,
                     image_data, progress_callback=None):
        initiate_request = {
            "sessionId": session_id,
            "title": title,
            "description": None,
            "imageKind": image_kind,
            "imageMetadata": image_metadata_json,
            "totalSize": len(image_data),
            "contentType": "image/jpeg",
        }

        init_response = self.initiate_upload(initiate_request)
        chunk_size = init_response["chunkSize"]
        total_parts = init_response["totalParts"]
        upload_id = init_response["uploadId"]

        for part in range(1, total_parts + 1):
            offset = (part - 1) * chunk_size
            chunk = image_data[offset:offset + chunk_size]
            self.upload_part(upload_id, part, chunk)
            if progress_callback:
                progress_callback(part, total_parts)

        return self.complete_upload(upload_id)

    def _get(self, path):
        url = self.base_url + path
        try:
            resp = self.session.get(url, timeout=TIMEOUT)
        except requests.RequestException as e:
            raise SpectroSolHubException(f"Failed to connect to SpectroSolHub: {e}")

        if resp.status_code == 200:
            return resp.json()
        raise SpectroSolHubException(resp.text, resp.status_code)

    def _post(self, path, body=None, expected_status=200):
        url = self.base_url + path
        try:
            if body is not None:
                resp = self.session.post(
                    url,
                    json=body,
                    headers={"Content-Type": "application/json"},
                    timeout=TIMEOUT,
                )
            else:
                resp = self.session.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    timeout=TIMEOUT,
                )
        except requests.RequestException as e:
            raise SpectroSolHubException(f"Failed to connect to SpectroSolHub: {e}")

        if resp.status_code == expected_status:
            return resp.json()
        raise SpectroSolHubException(resp.text, resp.status_code)
