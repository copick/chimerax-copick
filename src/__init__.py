# vim: set expandtab shiftwidth=4 softtabstop=4:


from chimerax.core.toolshed import BundleAPI


class _MyAPI(BundleAPI):
    api_version = 1


# Create the ``bundle_api`` object that ChimeraX expects.
bundle_api = _MyAPI()
