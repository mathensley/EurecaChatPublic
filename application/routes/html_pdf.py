"""Endpoint independente para exportar HTML em PDF."""

from quart import Blueprint, Response, jsonify, request

from application.services.html_pdf_tools import render_html_to_pdf


bp = Blueprint("html_pdf", __name__, url_prefix="/api")


@bp.post("/html-to-pdf")
async def html_to_pdf():
    uploaded = (await request.files).get("file")
    if uploaded is None or not uploaded.filename.lower().endswith((".html", ".htm")):
        return jsonify({"error": "Envie um arquivo HTML no campo 'file'"}), 400

    content = uploaded.read()
    if not content:
        return jsonify({"error": "O arquivo HTML está vazio"}), 400
    orientation = request.args.get("orientation", "V").upper()
    try:
        pdf = render_html_to_pdf(content, orientation=orientation)  # type: ignore[arg-type]
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        return jsonify({"error": str(error)}), 422

    filename = f"{uploaded.filename.rsplit('.', 1)[0]}.pdf"
    return Response(
        pdf,
        content_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
