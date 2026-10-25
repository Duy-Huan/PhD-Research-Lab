import io
import unittest
from PIL import Image
from fastapi.testclient import TestClient

from backend.app import app
from backend.knowledge import attachments as AT
from backend.providers import mcp_tools


class TestImageAttachmentsAndVisionTool(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _create_sample_image_bytes(self, width=100, height=80, color=(50, 100, 150)):
        buf = io.BytesIO()
        img = Image.new("RGB", (width, height), color)
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_upload_image_and_metadata_extraction(self):
        img_bytes = self._create_sample_image_bytes(240, 160)
        uploaded = AT.add_upload("experiment_plot.png", img_bytes)

        self.assertIn("id", uploaded)
        self.assertEqual(uploaded["kind"], "image")
        self.assertEqual(uploaded["width"], 240)
        self.assertEqual(uploaded["height"], 160)
        self.assertEqual(uploaded["format"], "PNG")
        self.assertEqual(uploaded["media_type"], "image/png")

        # Test base64 extraction
        b64 = AT.get_base64_image(uploaded["id"])
        self.assertEqual(b64["media_type"], "image/png")
        self.assertTrue(len(b64["data"]) > 0)
        self.assertEqual(b64["width"], 240)
        self.assertEqual(b64["height"], 160)

    def test_image_analysis_tool(self):
        img_bytes = self._create_sample_image_bytes(300, 200, (255, 255, 255))
        uploaded = AT.add_upload("figure_architecture.png", img_bytes)

        analysis = AT.analyze_image_attachment(uploaded["id"], focus="check dimensions and layout")
        self.assertEqual(analysis["attachment_id"], uploaded["id"])
        self.assertEqual(analysis["dimensions"]["width"], 300)
        self.assertEqual(analysis["dimensions"]["height"], 200)
        self.assertEqual(analysis["aspect_ratio"], 1.5)
        self.assertIn("summary", analysis)

        # Call via MCP tools
        tool_res = mcp_tools.call("research_analyze_image", {"attachment_id": uploaded["id"], "focus": "inspect plot"})
        self.assertIn("structuredContent", tool_res)
        self.assertIn("provenance", tool_res["structuredContent"])
        self.assertEqual(tool_res["structuredContent"]["result"]["attachment_id"], uploaded["id"])

        # Test alias 'analyze_image'
        alias_res = mcp_tools.call("analyze_image", {"attachment_id": uploaded["id"]})
        self.assertEqual(alias_res["structuredContent"]["result"]["attachment_id"], uploaded["id"])

    def test_api_attachment_endpoints(self):
        img_bytes = self._create_sample_image_bytes(120, 100)
        uploaded = AT.add_upload("screenshot_test.png", img_bytes)
        att_id = uploaded["id"]

        # 1. GET /api/chat/attachments/{att_id}
        meta_res = self.client.get(f"/api/chat/attachments/{att_id}")
        self.assertEqual(meta_res.status_code, 200)
        meta_json = meta_res.json()
        self.assertEqual(meta_json["id"], att_id)
        self.assertEqual(meta_json["width"], 120)

        # 2. GET /api/chat/attachments/{att_id}/file
        file_res = self.client.get(f"/api/chat/attachments/{att_id}/file")
        self.assertEqual(file_res.status_code, 200)
        self.assertEqual(file_res.headers.get("content-type"), "image/png")
        self.assertEqual(len(file_res.content), len(img_bytes))

        # 3. POST /api/chat/attachments/{att_id}/analyze
        analyze_res = self.client.post(f"/api/chat/attachments/{att_id}/analyze", json={"focus": "verify structure"})
        self.assertEqual(analyze_res.status_code, 200)
        an_json = analyze_res.json()
        self.assertEqual(an_json["attachment_id"], att_id)
        self.assertEqual(an_json["dimensions"]["width"], 120)


if __name__ == "__main__":
    unittest.main()
