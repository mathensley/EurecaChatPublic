from pathlib import Path

from quart import Blueprint, abort, send_from_directory

bp = Blueprint("web", __name__)
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend" / "out"


async def _frontend_page(page: str):
    target = FRONTEND_DIR / page
    if target.is_file():
        response = await send_from_directory(FRONTEND_DIR, page)
        # O HTML aponta para assets versionados do Next. Ele não deve ficar em
        # cache entre deploys, ou pode carregar uma interface de uma build antiga.
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    abort(404)

@bp.route('/')
async def home():
    return await _frontend_page("index.html")

@bp.route('/sobre')
@bp.route('/sobre/')
async def sobre():
    return await _frontend_page("sobre/index.html")

@bp.route('/tutorial')
@bp.route('/tutorial/')
async def tutorial():
    return await _frontend_page("tutorial/index.html")

@bp.route('/login')
@bp.route('/login/')
async def login():
    return await _frontend_page("login/index.html")

@bp.route('/politica_termos')
@bp.route('/politica_termos/')
async def politica_termos():
    return await _frontend_page("politica_termos/index.html")


@bp.route('/_next/<path:asset>')
async def next_asset(asset: str):
    return await send_from_directory(FRONTEND_DIR / "_next", asset)


@bp.route('/favicon.ico')
async def favicon():
    return await send_from_directory(FRONTEND_DIR, "ufcg.png")


@bp.route('/<path:asset>')
async def public_frontend_asset(asset: str):
    """Serve somente arquivos públicos gerados pelo export estático do Next."""
    target = FRONTEND_DIR / asset
    if FRONTEND_DIR.is_dir() and target.is_file():
        return await send_from_directory(FRONTEND_DIR, asset)
    abort(404)
