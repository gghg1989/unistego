'''
Created on Jan 3, 2014

@author: ivan
'''

import io
from unistego.exceptions import ErrorNotFinished
from unistego.strategy import JoinersHidingStrategy, JoinersUnhidingStrategy, AltSpaceHidingStrategy,\
    AltSpaceUnhidingStrategy, UnfinishedString
from .compress import Zlib
import six
from unistego import html_parser

PRESETS={'joiners': {'hider': {'strategy_class':JoinersHidingStrategy,},
                     'unhider':{'strategy_class':JoinersUnhidingStrategy},
                     'help': 'Plain text, message is hidden with ZERO WIDTH JOINER and ZERO WIDTH NON_JOINER characters'},
         'joiners+zlib': {'hider': {'strategy_class':JoinersHidingStrategy,},
                     'unhider':{'strategy_class':JoinersUnhidingStrategy},
                     'help': 'Plain text, message is hidden with ZERO WIDTH JOINER and ZERO WIDTH NON_JOINER characters, before hidding message is compressed with zlib'},
         'spaces': {'hider': {'strategy_class':AltSpaceHidingStrategy, },
                    'unhider': {'strategy_class':AltSpaceUnhidingStrategy},
                    'help': 'Plain text, message is hidden by alternating regular spaces and THREE-PER-EM SPACE'
                    },
         'spaces+zlib': {'hider': {'strategy_class':AltSpaceHidingStrategy, 'compress_class':Zlib, 'level':9},
                    'unhider': {'strategy_class':AltSpaceUnhidingStrategy,  'compress_class':Zlib},
                    'help': 'Plain text, message is hidden by alternating regular spaces and THREE-PER-EM SPACE, before hidding message is compressed with zlib'
                    }
         }

def list_presets():
    names=PRESETS.keys()
    names.sort()
    return [(name, PRESETS[name].get('help')) for name in names]

def get_hider(out_text_stream, secret, preset, **kwargs):
    kwargs.update(PRESETS[preset]['hider'])
    return HidingStream(out_text_stream, secret, **kwargs)

def get_hider_html(out_text_stream, secret, preset, **kwargs):
    kwargs.update(PRESETS[preset]['hider'])
    return HtmlHidingStream(out_text_stream, secret, **kwargs)

def get_unhider(in_text_stream, preset, **kwargs):
    kwargs.update(PRESETS[preset]['unhider'])
    return UnhidingStream(in_text_stream,**kwargs)

def get_unhider_html(in_text_stream, preset, **kwargs):
    kwargs.update(PRESETS[preset]['unhider'])
    return HtmlUnhidingStream(in_text_stream,**kwargs)



class HidingStream(io.TextIOBase):
    
    def __init__(self, out_text_stream, secret, strategy_class, compress_class=None, **kwargs):
        self._out=out_text_stream
        if compress_class:
            compressor=compress_class(**kwargs)
            if isinstance(secret, six.string_types):
                secret=secret.encode('utf-8')
            secret=compressor.compress(secret)
            
        self._hider=strategy_class(secret, **kwargs)
        
    def readable(self):
        return False
    
    def seekable(self):
        return False
    
    def flush(self):
        raise io.UnsupportedOperation
    
    def write(self, s):
        self._out.write(self._hider.hide(s))
        
    def remains_to_hide(self):
        """ returns number of bits which are yet to be hidden in text """
        return self._hider.remaining_bits
    
    def close(self, force=False):
        if self._hider.remaining_bits>0 and not force:
            raise ErrorNotFinished('Secret message has not been hidden - %d bits remains')
        remaining=self._hider.flush()
        if remaining:
            self._out.write(remaining)
        self._out.close()
        
class HtmlHidingStream(HidingStream):
    
    def __init__(self, out_text_stream, secret, strategy_class, compress_class=None, **kwargs):
        fragment=kwargs.pop('fragment', False)
        self._parser=html_parser.Parser(self._write_text, self._write_markup, fragment=fragment)
        kwargs['delayed_cb']=self._resolve_delayed
        super(HtmlHidingStream, self).__init__(out_text_stream, secret, strategy_class, 
                                               compress_class=compress_class, **kwargs)
        self._wait=False
        self._delayed=[]
        
    def _resolve_delayed(self, ch=None):  
        if ch:
            self._out.write(ch)
        for t in self._delayed:
            self._out.write(t)
        self._delayed=[]
        self._wait=False
          
    def _write_text(self, data):
        txt=self._hider.hide(data)
        if isinstance(txt, UnfinishedString):
            self._wait=True
        self._out.write(txt)
        
    def _write_markup(self, data):
        if self._wait:
            self._delayed.append(data)
        else:
            self._out.write(data)
        
    def write(self,s):
        self._parser.feed(s)
        
    def close(self, force=False):
        self._parser.close()
        super(HtmlHidingStream,self).close(force=force)
        
        
        
class UnhidingStream(io.TextIOBase):
    def __init__(self, in_text_stream, strategy_class, compress_class=None, **kwargs):
        self._in=in_text_stream
        self._unhider=strategy_class( **kwargs)
        if compress_class:
            self._compressor=compress_class(**kwargs)
        else:
            self._compressor=None
        
    def writable(self):
        return False
    
    def seekable(self):
        return False
    
    def read(self, n=-1):
        txt=self._in.read(n)
        if txt:
            self._unhider.unhide(txt)
        return txt
    
    def readline(self, limit=-1):
        txt=self._in.readline(limit)
        if txt:
            self._unhider.unhide(txt)
        return txt
    
    def close(self):
        self._in.close()
    
    def get_message(self):
        msg=self._unhider.get_message()
        if self._compressor:
            msg=self._compressor.decompress(msg)
        return msg
        
        
class HtmlUnhidingStream(UnhidingStream):   
    def __init__(self, in_text_stream, strategy_class, compress_class=None, **kwargs):
        fragment=kwargs.pop('fragment', False)
        self._parser=html_parser.Parser(self._read_text,lambda s: None, fragment=fragment)
        super(HtmlUnhidingStream,self).__init__(in_text_stream, strategy_class, compress_class=compress_class, **kwargs) 
    
    def read(self, n=-1):
        txt=self._in.read(n)
        if txt:
            self._parser.feed(txt)
        return txt
    
    def readline(self, limit=-1):
        txt=self._in.readline(limit)
        if txt:
            self._parser.feed(txt)
        return txt
    
    def _read_text(self, txt):
        self._unhider.unhide(txt)
    
    
        