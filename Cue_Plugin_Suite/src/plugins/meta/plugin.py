from src.plugins.stubs import NotImplementedCuePlugin


class MetaGraphPlugin(NotImplementedCuePlugin):
    id = "metaGraph"
    name = "Meta Graph API"
    platform = "facebook"


class InstagramHashtagPlugin(NotImplementedCuePlugin):
    id = "instagramHashtag"
    name = "Instagram Hashtag Search"
    platform = "instagram"

