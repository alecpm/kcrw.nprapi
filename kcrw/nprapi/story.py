import logging
from urllib2 import build_opener
from urllib import quote_plus
# Some exception handling to support both python 2.4 and 2.5+
try:
    from xml.etree.cElementTree import fromstring
except ImportError:
    from cElementTree import fromstring
try:
    from json import loads
except ImportError:
    from simplejson import loads

# Configure default null logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass

npr_log = logging.getLogger('kcrw.nprapi')
npr_log.setLevel(logging.INFO)
npr_log.addHandler(NullHandler())

BASE_URL = 'http://api.npr.org/query'
OUTPUT_FORMATS = ('NPRML', 'RSS', 'MediaRSS', 'Podcast', 'ATOM', 'JSON',
                  'HTML', 'JS')
QUERY_TERMS = (
    # query input
    'id', 'date', 'startDate', 'endDate', 'orgId', 'searchTerm', 'searchType',
    # output control
    'fields', 'callback', 'sort','startNum', 'numResults', 'action',
    'requiredAssets', 'title', 'remap','blah'
    )


class NPRError(Exception):
    """An error response from the NPR API.

    :param code: The NPR error code
    :param text: The NPR error message
    """

    def __init__(self, code, text=u''):
        self.code = code
        self.text = text

    def __str__(self):
        """Returns the error code and message."""
        return '%s - %s'%(self.code, self.text)


class StoryAPI(object):
    """Makes requests to the NPR Story API.

    :param api_key: Your NPR API key string, you must register to get this.
    :param output_format: The output format type.  Accepts any of the values
        in :const:`OUTPUT_FORMATS`, which are described in the
        `NPR API input reference <http://www.npr.org/api/inputReference.php>`_.
    """

    def __init__(self, api_key, output_format=None):
        self.api_key = api_key
        if output_format is not None:
            assert output_format in OUTPUT_FORMATS, 'Invalid output format'
        self.output_format = output_format
        # We construct a URL opener so we can easily swap it out
        # when unit testing
        self.opener = build_opener()

    def _make_url(self, query):
        """Construct a url for the given query parameters"""
        if self.output_format:
            query['output'] = self.output_format
        query['apiKey'] = self.api_key
        url_query = '&'.join('='.join(quote_plus(str(i)) for i in pair)
                             for pair in query.iteritems())
        return BASE_URL + '?' + url_query

    def query(self, ids, **kw):
        """Request data from the NPR API. Valid query parameters
        listed in the QUERY_TERMS constant.  Returns the response
        string after checking for errors.

        :param ids: An integer or string story id or a list of such ids
        :param kw: Accepts any of the NPR query parameters listed in
          :const:`QUERY_TERMS`.  These are described in detail in the
          `NPR API input reference <http://www.npr.org/api/inputReference.php>`_.
          All of these parameters must be strings or integers, except for
          the *fields* parameter which may be a list of field names.
        :except: Raises an :class:`NPRError` when an error response is
          returned by the NPR API.  Raises an :class:`urllib2.URLError` or an
          :class:`urllib2.HTTPError` when there is a problem accessing the
          NPR API service.
        :rtype: string
        """
        query = kw.copy()
        # If the ids are a list, convert to a string
        if not isinstance(ids, basestring) and hasattr(ids, '__iter__'):
            ids = ','.join(str(i) for i in ids)
        query['id'] = ids

        # We expect a list of field names for 'fields', convert to a string
        if not isinstance(query.get('fields', ''), basestring):
            query['fields'] = ','.join(query['fields'])

        # Filter so we have only allowed terms and terms with non-null
        # values
        allowed_terms = dict((term,None) for term in QUERY_TERMS)
        query = dict((k,v) for k,v in query.iteritems()
                         if k in allowed_terms and v is not None)

        # Make the request
        response = self.opener.open(self._make_url(query))
        response_text = response.read()

        # check for errors
        if response_text.startswith('<?xml') and 'message' in response_text:
            xml = fromstring(response_text)
            messages = xml.findall('message')
            for message in messages:
                text = message.find('text').text
                if message.get('level') == 'error':
                    # Raise the error
                    raise NPRError(message.get('id'), text)
                else:
                    # Log warning message
                    npr_log.warning('NPR API log: %s: %s - %s',
                                    message.get('level').upper(),
                                    message.get('id'), text)
        return response_text


class StoryMapping(object):
    """Uses the NPR API's JSON output to generate a simple data
    structure containing a list of NPR stories.

    The query method stores the full JSON-esque mapping in the
    :attr:`data` attribute and returns the list of story
    mappings. Additionally, a few properties are available on the
    class to allow easy retrieval of additional API metadata.

    :param api_key: Your NPR API key string, you must register to get this.
    :param prune_text_nodes: If this is set to true any single entry
      dictionaries in the query result with only the key ``$text``
      will be replaced with the value only.  This simplifies the data
      structure and makes it appear more 'pythonic' and less XML-ish.
      """

    def __init__(self, api_key, prune_text_nodes=True):
        self.story_api = StoryAPI(api_key, 'JSON')
        self.data = {}
        self._prune_text_nodes = prune_text_nodes

    def query(self, ids, **kw):
        """Make a query to the API, returns a list of story
        dictionaries and updates the :attr:`data` attribute.

        :param ids: An integer or string story id or a list of such ids
        :param kw: Accepts any of the NPR query parameters listed in
          :const:`QUERY_TERMS`.  These are described in detail in the
          `NPR API input reference <http://www.npr.org/api/inputReference.php>`_.
          All of these parameters must be strings or integers, except for
          the *fields* parameter which may be a list of field names.
        :except: Raises an :class:`NPRError` when an error response is
          returned by the NPR API.  Raises an :class:`urllib2.URLError` or an
          :class:`urllib2.HTTPError` when there is a problem accessing the
          NPR API service.
        :rtype: list of story mappings
        """
        self.data = loads(self.story_api.query(ids, **kw))
        if self._prune_text_nodes:
            self._process_data(self.data)
        return self.stories

    def _process_data(self, data):
        """Because of it's XML origins, the json data contains many
        entries with values of the form {'$text': ...}; this is not
        desirable, so we replace these single item dictionaries with
        the text value alone.  Entries with multiple item dictionaries
        will still have a '$text' key.  Additionally, the 'link'
        elements can be better represented as a mapping with the
        'type' as the key, than a list of dicts with type and $text
        keys.

        This modifies mutable data-structures in-place.
        """
        # Recurse through all mappings and lists, looking for single
        # item dictionaries with only the key '$text'
        if hasattr(data, 'keys'):
            for item in data:
                value = data[item]
                keys = hasattr(value, 'keys') and value.keys()
                if keys and len(keys) == 1 and keys[0] == '$text':
                    data[item] = value['$text']
                elif keys:
                    self._process_data(value)
                elif isinstance(value, list) and item == 'link':
                    # Lists of links are structured in an almost useless manner.
                    # Turn them into a sensible mapping
                    entries = set(value[0].keys())
                    if entries == set(('type', '$text')):
                        links = {}
                        for link in value:
                            links[link['type']] = link['$text']
                        data[item] = links
                elif isinstance(value, list):
                    self._process_data(value)
        elif isinstance(data, list):
            for item in data:
                self._process_data(item)

    @property
    def version(self):
        """The API version of the last query response.  This will not
        have a value until :meth:`query` is called."""
        return self.data.get('version', '')

    @property
    def title(self):
        """The title of the query response feed.  This will not have a
        value until :meth:`query` is called."""
        if 'list' not in self.data:
            return ''
        value = self.data['list']['title']
        if not self._prune_text_nodes:
            value = value['$text']
        return value

    @property
    def description(self):
        """The description of the query response feed.  This will not
        have a value until :meth:`query` is called."""
        if 'list' not in self.data:
            return ''
        value = self.data['list']['teaser']
        if not self._prune_text_nodes:
            value = value['$text']
        return value

    @property
    def stories(self):
        """The list of stories, this is identical to the last return
        value of :meth:`query`.  This will not have a value until
        :meth:`query` is called.
        """
        if 'list' in self.data:
            return self.data['list']['story']
        else:
            return []
