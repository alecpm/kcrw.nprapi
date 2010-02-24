from urlparse import urlsplit
from StringIO import StringIO
from kcrw.nprapi.story import NPRError
try:
    from json import dumps
except ImportError:
    from simplejson import dumps
try:
    from urlparse import parse_qs
except ImportError:
    from cgi import parse_qs

# We have mock responses for ids 1, 1234567 and 3456789 in both NPRML
# and JSON formats, as well as an error response, which is always in
# XML
MOCK_RESPONSES = {
    '1': dumps({"version": u"0.93",
                "list": {"title": {"$text": u"Test Data"},
                         "teaser": {"$text": u"More Test Data"},
                         "story": [{"id": u"1234567",
                                    "title": {"$text": u"Some other title"},
                                    "link": [{"type": "html",
                                              "$text": u"http://..."},
                                             {"type": "api",
                                              "$text": u"http://..."}]},
                                   {"id": u"3456789",
                                    "title": {"$text": u"Some other title"},
                                    "link": [{"type": u"html",
                                              "$text": "http://..."},
                                             {"type": "api",
                                              "$text": u"http://..."}]},
                                   ]
                         }
                }),
    'error':

"""<?xml version="1.0" encoding="UTF-8"?>
<xml>
  <message id="XXX" level="error">
    <text>Some Error!!</text>
    <timestamp>1266014530.84</timestamp>
  </message>
</xml> """,

    'warning':

"""<?xml version="1.0" encoding="UTF-8"?>
<xml>
  <message id="1000" level="my warning">
    <text>You have been warned</text>
    <timestamp>1266014530.84</timestamp>
  </message>
</xml> """,
    }

class MockNPROpener(object):
    """Acts as a urllib2 url opener for the NPR API service, returns
    demo data."""
    last_url = ''

    def open(self, url):
        """Returns fake NPR data based on query parameters."""
        # Set the current url for introspection
        self.last_url = url
        # Get the id from the URL
        parts = urlsplit(url)
        query = parse_qs(parts[3])
        ids = query['id'][0]
        # If we requested an error response, send it, otherwise just
        # send something
        if ids in ('error', 'warning'):
            return StringIO(MOCK_RESPONSES[ids])
        return StringIO('Nonsense')

class MockStoryAPI(object):

    def __init__(self, api_key, output_format=None):
        self.format = output_format or 'NPRML'

    def query(self, ids, **kw):
        # Convert id input to a string
        if isinstance(ids, int):
            ids = str(ids)
        if not isinstance(ids, basestring):
            ids = ','.join(str(i) for i in ids)
        output = MOCK_RESPONSES.get(ids)
        # The StoryAPI raises an error if it gets an error response.
        if ids == 'error':
            raise NPRError('XXX', 'Some Error!!')
        return output
