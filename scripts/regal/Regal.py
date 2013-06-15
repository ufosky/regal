#!/usr/bin/python -B

from string       import Template, upper, replace
from ApiUtil      import outputCode
from ApiUtil      import typeIsVoid
from ApiUtil      import typeIsVoidPointer
from ApiUtil      import toLong
from ApiUtil      import hexValue
from ApiCodeGen   import *
from ApiRegal     import logFunction
from Emu          import emuFindEntry, emuCodeGen

from RegalContext     import emuRegal
from RegalContextInfo import cond
from RegalSystem      import regalSys

publicHeaderTemplate = Template( '''${AUTOGENERATED}
${LICENSE}

#ifndef __REGAL_DECLARATIONS_H
#define __REGAL_DECLARATIONS_H

${REGAL_SYS}

#if REGAL_SYS_WGL
# define REGAL_CALL __stdcall
#else
# define REGAL_CALL
#endif

#ifndef GLAPIENTRY
#define GLAPIENTRY REGAL_CALL
#endif

#ifdef _WIN32
#  if REGAL_DECL_EXPORT
#    define REGAL_DECL
#  else
#    define REGAL_DECL __declspec(dllimport)
#  endif
#elif defined(__GNUC__) && __GNUC__>=4
#  if REGAL_DECL_EXPORT
#    define REGAL_DECL __attribute__ ((visibility("default")))
#  else
#    define REGAL_DECL
#  endif
#elif defined(__SUNPRO_C) || defined(__SUNPRO_CC)
#  if REGAL_DECL_EXPORT
#    define REGAL_DECL __global
#  else
#    define REGAL_DECL
#  endif
#else
#  define REGAL_DECL
#endif

/* Plugins need the GL API as externs with plugin_ prefix */

#ifdef REGAL_PLUGIN_MODE
#undef  REGAL_DECL
#define REGAL_DECL extern
#endif

#endif /* __REGAL_DECLARATIONS_H */

#ifndef __${HEADER_NAME}_H__
#define __${HEADER_NAME}_H__

/* Skip OpenGL API if another header was included first. */

#if !defined(__gl_h_) && !defined(__GL_H__) && !defined(__X_GL_H) && !defined(__gl2_h_) && !defined(__glext_h_) && !defined(__GLEXT_H_) && !defined(__gl_ATI_h_) && !defined(_OPENGL_H)

#define __gl_h_
#define __gl2_h_
#define __GL_H__
#define __X_GL_H
#define __glext_h_
#define __GLEXT_H_
#define __gl_ATI_h_
#define _OPENGL_H

#if REGAL_SYS_GLX
#include <X11/Xdefs.h>
#include <X11/Xutil.h>
typedef XID GLXDrawable;
#endif

#if REGAL_SYS_EGL && REGAL_SYS_X11
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#endif

#ifdef __cplusplus
extern "C" {
#endif

#include <stddef.h>
#if defined(_WIN32)
  typedef __int64 int64_t;
  typedef unsigned __int64 uint64_t;
  #if defined(REGAL_SYS_WGL_DECLARE_WGL) && !defined(_WINDEF_)
    struct HDC__ {int unused;};
    typedef struct HDC__* HDC;
    struct HGLRC__ {int unused;};
    typedef struct HGLRC__* HGLRC;
  #endif
#else
  #include <inttypes.h>
#endif

${API_TYPEDEF}

/* TODO: make this automatic? */

typedef void (REGAL_CALL *GLDEBUGPROCAMD)(GLuint id, GLenum category, GLenum severity, GLsizei length, const GLchar *message, GLvoid *userParam);
typedef void (REGAL_CALL *GLDEBUGPROCARB)(GLenum source, GLenum type, GLuint id, GLenum severity, GLsizei length, const GLchar *message, GLvoid *userParam);
typedef void (REGAL_CALL *GLDEBUGPROC)(GLenum source, GLenum type, GLuint id, GLenum severity, GLsizei length, const GLchar *message, GLvoid *userParam);

typedef void (*GLLOGPROCREGAL)(GLenum stream, GLsizei length, const GLchar *message, GLvoid *context);

#if REGAL_SYS_GLX
typedef void (*__GLXextFuncPtr)(void);
#endif

${API_ENUM}

${API_FUNC_DECLARE}

#ifdef __cplusplus
}
#endif

#endif /* __gl_h_ etc */
#endif /* __REGAL_H__ */

#ifndef __REGAL_API_H
#define __REGAL_API_H

#if REGAL_SYS_PPAPI
#include <stdint.h>
struct PPB_OpenGLES2;
typedef int32_t RegalSystemContext;
#else
typedef void * RegalSystemContext;
#endif

/* Regal-specific API... try to keep this minimal
   this is a seperate include guard to work nicely with RegalGLEW.h
*/

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*RegalErrorCallback)(GLenum);
REGAL_DECL RegalErrorCallback RegalSetErrorCallback( RegalErrorCallback callback );

/*  RegalConfigure is optional.
 */

REGAL_DECL void RegalConfigure(const char *json);

/*  RegalShareContext is optional.  It must be called before any call
 *  to RegalMakeCurrent.  It specifies that a context is sharing state
 *  with one already known to Regal.
 */

REGAL_DECL void RegalShareContext(RegalSystemContext ctx, RegalSystemContext other);

/*  RegalMakeCurrent
 *
 */

#if REGAL_SYS_PPAPI
REGAL_DECL void RegalMakeCurrent( RegalSystemContext ctx, struct PPB_OpenGLES2 *ppb_interface );
#else
REGAL_DECL void RegalMakeCurrent( RegalSystemContext ctx );
#endif

/*  RegalDestroyContext - release resources used by Regal context.
 *
 */

REGAL_DECL void RegalDestroyContext(RegalSystemContext ctx);

#ifdef __cplusplus
}
#endif

#endif /* __REGAL_API_H */
''')

def generatePublicHeader(apis, args):

  apiTypedef     = apiTypedefCode( apis, args )
  apiEnum        = apiEnumCode(apis, args)                 # CodeGen for API enums
  apiFuncDeclare = apiFuncDeclareCode( apis, args )        # CodeGen for API functions

  # Output

  substitute = {}
  substitute['LICENSE']          = args.license
  substitute['AUTOGENERATED']    = args.generated
  substitute['COPYRIGHT']        = args.copyright
  substitute['HEADER_NAME']      = "REGAL"
  substitute['REGAL_SYS']        = regalSys
  substitute['API_TYPEDEF']      = apiTypedef
  substitute['API_ENUM']         = apiEnum
  substitute['API_FUNC_DECLARE'] = apiFuncDeclare

  outputCode( '%s/Regal.h' % args.incdir, publicHeaderTemplate.substitute(substitute))

def apiFuncDefineCode(apis, args):

  #

  code = ''
  for api in apis:

    tmp = []
    for function in api.functions:

      name       = function.name
      params     = paramsDefaultCode(function.parameters, True)
      callParams = paramsNameCode(function.parameters)
      rType      = typeCode(function.ret.type)
      rTypes     = rType.strip()
      category   = getattr(function, 'category', None)
      version    = getattr(function, 'version', None)

      if category:
        category = category.replace('_DEPRECATED', '')
      elif version:
        category = version.replace('.', '_')
        category = 'GL_VERSION_' + category

      c = ''
      c += 'REGAL_DECL %sREGAL_CALL %s(%s) \n{\n' % (rType, name, params)

      emue = [ emuFindEntry( function, i['formulae'], i['member'] ) for i in emuRegal ]

      if function.needsContext:
        c += '  RegalContext *_context = REGAL_GET_CONTEXT();\n'
        c += listToString(indent(emuCodeGen(emue,'prefix'),'  '))
        c += '  %s\n' % logFunction( function, 'App' )
        c += '  if (!_context) return'
        if typeIsVoid(rType):
          c += ';\n'
        else:
          if rTypes in api.defaults:
            c += ' %s;\n' % ( api.defaults[rTypes] )
          else:
            if rType[-1]=='*' or typeIsVoidPointer(rType):
              c += ' NULL;\n'
            else:
              c += ' (%s) 0;\n' % ( rTypes )

        c += listToString(indent(emuCodeGen(emue,'impl'),'  '))

        if getattr(function,'regalRemap',None)!=None and (isinstance(function.regalRemap, list) or isinstance(function.regalRemap, str) or isinstance(function.regalRemap, unicode)):

          # For an ES1 context, pass the call into the dispatch layers...

          if function.category in ['GL_REGAL_ES1_0_compatibility','GL_REGAL_ES1_1_compatibility']:
            c += '  #if REGAL_SYS_ES1\n'
            c += '  if (_context->isES1()) // Pass-through for ES1 only\n'
            c += '  {\n'
            c += '    DispatchTableGL *_next = &_context->dispatcher.front();\n'
            c += '    RegalAssert(_next);\n    '
            if not typeIsVoid(rType):
              c += 'return '
            c += '_next->call(&_next->%s)(%s);\n' % ( name, callParams )
            if typeIsVoid(rType):
              c += '    return;\n'
            c += '  }\n'
            c += '  #endif\n'

          # For ES2 or GL context, remap the ES1 call

          c += '  '
          if not typeIsVoid(rType):
            c += 'return '
          if isinstance(function.regalRemap, list):
            c += '\n  '.join(function.regalRemap) + '\n'
          else:
            c += '%s;\n'%(function.regalRemap)
        else:
          if getattr(function,'regalOnly',False)==False:
            t = ''
            t += 'DispatchTableGL *_next = &_context->dispatcher.front();\n'
            t += 'RegalAssert(_next);\n'

            t += listToString(indent(emuCodeGen(emue,'pre'),''))

            if not typeIsVoid(rType):
              t += 'return '
            t += '_next->call(&_next->%s)(%s);\n' % ( name, callParams )

            t += listToString(indent(emuCodeGen(emue,'post'),''))

            for i in emue:
              if i!=None and i['cond']!=None:
                t = wrapCIf(i['cond'],indent(t))

            c += indent(t)

            c += listToString(indent(emuCodeGen(emue,'suffix'),'  '))

      else:
        c += '  %s\n' % logFunction(function, 'App' )
        c += listToString(indent(emuCodeGen(emue,'prefix'),'  '))

        if getattr(function,'regalOnly',False)==False:
          c += '  DispatchTableGlobal *_next = &dispatcherGlobal.front();\n'
          c += '  RegalAssert(_next);\n'

          if not typeIsVoid(rType):
            if rTypes in api.defaults:
              c += '  %s ret = %s;\n' % ( rTypes, api.defaults[rTypes] )
            else:
              if rType[-1]=='*' or typeIsVoidPointer(rType):
                c += '  %s ret = NULL;\n' % rTypes
              else:
                c += '  %s ret = (%s) 0;\n' % ( rTypes, rTypes )

          c += listToString(indent(emuCodeGen(emue,'impl'),'  '))
          c += '  '
          if not typeIsVoid(rType):
            c += 'ret = '
          c += '_next->call(&_next->%s)(%s);\n' % ( name, callParams )

        c += listToString(indent(emuCodeGen(emue,'init'),'  '))

        c += listToString(indent(emuCodeGen(emue,'suffix'),'  '))
        if not typeIsVoid(rType):
          c += '  return ret;\n'
      c += '}\n\n'

      tmp.append( (category, indent(c,'  ') ) )

    tmp = listToString(unfoldCategory(tmp,'  /* %s */'))

    if api.name in cond:
      tmp = wrapIf(cond[api.name], tmp)

    code += tmp

  return code

def apiTypedefCode( apis, args ):

  code = ''
  for api in apis:
    code += '\n'
    if api.name in cond:
      code += '#if %s\n' % cond[api.name]
    if api.name == 'wgl':
      code += '#ifdef  REGAL_SYS_WGL_DECLARE_WGL\n'
      code += '#ifndef _WINDEF_\n'
    for typedef in api.typedefs:

      if api.name == 'wgl' and typedef.name=='GLYPHMETRICSFLOAT':
        code += '#endif\n'
        code += '#ifndef _WINGDI_\n'
      if api.name == 'wgl' and typedef.name=='HPBUFFERARB':
        code += '#endif\n'

      if re.search( '\(\s*\*\s*\)', typedef.type ):
        code += 'typedef %s;\n' % ( re.sub( '\(\s*\*\s*\)', '(*%s)' % typedef.name, typedef.type ) )
      else:
        code += 'typedef %s %s;\n' % ( typedef.type, typedef.name )

    if api.name == 'wgl':
      code += '#endif // REGAL_SYS_WGL_DECLARE_WGL\n'
    if api.name in cond:
      code += '#endif // %s\n' % cond[api.name]
    code += '\n'

  return code

# CodeGen for custom API definitions.

def apiEnumCode( apis, args ):

  code = ''
  for api in apis:
    code += '\n'
    if api.name in cond:
      code += '#if %s\n' % cond[api.name]
    if api.name == 'wgl':
      code += '#if REGAL_SYS_WGL_DECLARE_WGL\n'
    for enum in api.enums:
      if enum.name == 'defines':
        pass
      else:
        code += '\ntypedef enum _%s {\n' % enum.name
        for enumerant in enum.enumerants:
          code += '  %s = %s,\n' % ( enumerant.name, enumerant.value )
        code += '} %s;\n\n' % enum.name
    if api.name == 'wgl':
      code += '#endif // REGAL_SYS_WGL_DECLARE_WGL\n'
    if api.name in cond:
      code += '#endif // %s\n' % cond[api.name]
    code += '\n'

  return code

# CodeGen for API function declaration.

def apiFuncDeclareCode(apis, args):
  code = ''

  for api in apis:

    d = [] # defines
    e = [] # enums
    t = [] # function pointer typedefs
    m = [] # mangled names for REGAL_NAMESPACE support
    f = [] # gl names
    p = [] # plugin names for REGAL_PLUGIN_MODE support

    for enum in api.enums:
      if enum.name == 'defines':
        for enumerant in enum.enumerants:
          value = toLong(enumerant.value)
          if value==None:
            value = enumerant.value

          # Don't bother with decimal for 0-10
          if isinstance(value, long) and value>=10:
            e.append((enumerant.category, '#define %s %s /* %s */'%(enumerant.name,hexValue(value),value)))
          else:
            e.append((enumerant.category, '#define %s %s'%(enumerant.name,hexValue(value))))

    for function in api.functions:

      name   = function.name
      params = paramsDefaultCode(function.parameters, True)
      rType  = typeCode(function.ret.type)
      category  = getattr(function, 'category', None)
      version   = getattr(function, 'version', None)

      if category:
        category = category.replace('_DEPRECATED', '')
      elif version:
        category = version.replace('.', '_')
        category = 'GL_VERSION_' + category

      t.append((category,funcProtoCode(function, version, 'REGAL_CALL', True)))
      m.append((category,'#define %-35s r%-35s' % (name, name) ))
      f.append((category,'REGAL_DECL %sREGAL_CALL %s(%s);' % (rType, name, params) ))
      p.append((category,'REGAL_DECL %sREGAL_CALL plugin_%s(%s);' % (rType, name, params) ))

    def cmpEnum(a,b):
      if a[0]==b[0]:
        aValue = a[1].split(' ')[2]
        bValue = b[1].split(' ')[2]
        if aValue==bValue:
          return cmp(a[1].split(' ')[1], b[1].split(' ')[1])
        else:
          return cmp(aValue,bValue)
      return cmp(a[0],b[0])

    def enumIfDef(category):
      return '#ifndef REGAL_NO_ENUM_%s'%(upper(category).replace(' ','_'))

    def typedefIfDef(category):
      return '#ifndef REGAL_NO_TYPEDEF_%s'%(upper(category).replace(' ','_'))

    def namespaceIfDef(category):
      return '#ifndef REGAL_NO_NAMESPACE_%s'%(upper(category).replace(' ','_'))

    def pluginIfDef(category):
      return '#ifndef REGAL_NO_PLUGIN_%s'%(upper(category).replace(' ','_'))

    def declarationIfDef(category):
      return '#ifndef REGAL_NO_DECLARATION_%s'%(upper(category).replace(' ','_'))

    categories = set()
    categories.update([ i[0] for i in e ])
    categories.update([ i[0] for i in t ])
    categories.update([ i[0] for i in m ])
    categories.update([ i[0] for i in p ])
    categories.update([ i[0] for i in f ])

    for i in categories:
      if len(i):
        cat = upper(i).replace(' ','_')

        d.append((i,'#if (defined(%s) || defined(REGAL_NO_ENUM) || defined(REGAL_NO_%s)) && !defined(REGAL_NO_ENUM_%s)'%(cat,cat,cat)))
        d.append((i,'#define REGAL_NO_ENUM_%s'%(cat)))
        d.append((i,'#endif'))
        d.append((i,''))

        d.append((i,'#if (defined(%s) || defined(REGAL_NO_TYPEDEF) || defined(REGAL_NO_%s)) && !defined(REGAL_NO_TYPEDEF_%s)'%(cat,cat,cat)))
        d.append((i,'#define REGAL_NO_TYPEDEF_%s'%(cat)))
        d.append((i,'#endif'))
        d.append((i,''))

        d.append((i,'#if (defined(%s) || !defined(REGAL_NAMESPACE) || defined(REGAL_NO_%s)) && !defined(REGAL_NO_NAMESPACE_%s)'%(cat,cat,cat)))
        d.append((i,'#define REGAL_NO_NAMESPACE_%s'%(cat)))
        d.append((i,'#endif'))
        d.append((i,''))

        d.append((i,'#if (defined(%s) || !defined(REGAL_PLUGIN_MODE) || defined(REGAL_NO_%s)) && !defined(REGAL_NO_PLUGIN_%s)'%(cat,cat,cat)))
        d.append((i,'#define REGAL_NO_PLUGIN_%s'%(cat)))
        d.append((i,'#endif'))
        d.append((i,''))

        d.append((i,'#if (defined(%s) || defined(REGAL_NO_DECLARATION) || defined(REGAL_NO_%s)) && !defined(REGAL_NO_DECLARATION_%s)'%(cat,cat,cat)))
        d.append((i,'#define REGAL_NO_DECLARATION_%s'%(cat)))
        d.append((i,'#endif'))
        d.append((i,''))

        d.append((i,'#ifndef %s'%(i)))
        d.append((i,'#define %s 1'%(i)))
        d.append((i,'#endif'))
        d.append((i,''))

    e.sort(cmpEnum)
    e = alignDefineCategory(e)
    e = ifCategory(e,enumIfDef)
    e = spaceCategory(e)

    t.sort()
    t = ifCategory(t,typedefIfDef)
    t = spaceCategory(t)

    m.sort()
    m = ifCategory(m,namespaceIfDef)
    m = spaceCategory(m)

    f.sort()
    f = ifCategory(f,declarationIfDef)
    f = spaceCategory(f)

    p.sort()
    p = ifCategory(p,pluginIfDef)
    p = spaceCategory(p)

    d.extend(e)
    d.extend(t)
    d.extend(m)
    d.extend(f)
    d.extend(p)

    tmp = listToString(unfoldCategory(d,'/**\n ** %s\n **/',lambda x,y: cmp(x[0], y[0])))

    if api.name == 'wgl':
      tmp = wrapIf('REGAL_SYS_WGL_DECLARE_WGL',tmp)
    if api.name in cond:
      tmp = wrapIf(cond[api.name], tmp)

    code += '%s\n'%(tmp)

  return code

# CodeGen for dispatch table init.

def apiGlobalDispatchFuncInitCode(apis, args):
  categoryPrev = None
  code = ''

  for api in apis:

    code += '\n'
    if api.name in cond:
      code += '#if %s\n' % cond[api.name]

    for function in api.functions:
      if function.needsContext:
        continue

      name   = function.name
      params = paramsDefaultCode(function.parameters, True)
      callParams = paramsNameCode(function.parameters)
      rType  = typeCode(function.ret.type)
      category  = getattr(function, 'category', None)
      version   = getattr(function, 'version', None)

      if category:
        category = category.replace('_DEPRECATED', '')
      elif version:
        category = version.replace('.', '_')
        category = 'GL_VERSION_' + category

      # Close prev category block.
      if categoryPrev and not (category == categoryPrev):
        code += '\n'

      # Begin new category block.
      if category and not (category == categoryPrev):
        code += '// %s\n\n' % category

      categoryPrev = category

      code += '  dispatchTableGlobal.%s = %s_%s;\n' % ( name, 'loader', name )

    if api.name in cond:
      code += '#endif // %s\n' % cond[api.name]
    code += '\n'

  # Close pending if block.
  if categoryPrev:
    code += '\n'

  return code

sourceTemplate = Template('''${AUTOGENERATED}
${LICENSE}

#include "pch.h" /* For MS precompiled header support */

#include "RegalUtil.h"

REGAL_GLOBAL_BEGIN

#include "RegalLog.h"
#include "RegalMac.h"
#include "RegalInit.h"
#include "RegalIff.h"
#include "RegalPush.h"
#include "RegalToken.h"
#include "RegalState.h"
#include "RegalClientState.h"
#include "RegalHelper.h"
#include "RegalPrivate.h"
#include "RegalDebugInfo.h"
#include "RegalContextInfo.h"
#include "RegalCacheShader.h"
#include "RegalCacheTexture.h"
#include "RegalScopedPtr.h"
#include "RegalFrame.h"
#include "RegalMarker.h"
#include "RegalDispatcherGL.h"
#include "RegalDispatcherGlobal.h"

using namespace REGAL_NAMESPACE_INTERNAL;
using namespace ::REGAL_NAMESPACE_INTERNAL::Logging;
using namespace ::REGAL_NAMESPACE_INTERNAL::Token;

extern "C" {

${API_FUNC_DEFINE}

}

REGAL_GLOBAL_END
''')

def generateSource(apis, args):

  # CodeGen for API functions.

  apiFuncDefine = apiFuncDefineCode( apis, args )
  globalDispatch = apiGlobalDispatchFuncInitCode( apis, args )

  # Output

  substitute = {}
  substitute['LICENSE']         = args.license
  substitute['AUTOGENERATED']   = args.generated
  substitute['COPYRIGHT']       = args.copyright
  substitute['API_FUNC_DEFINE'] = apiFuncDefine
  substitute['API_GLOBAL_DISPATCH_INIT'] = globalDispatch

  outputCode( '%s/Regal.cpp' % args.srcdir, sourceTemplate.substitute(substitute))

##############################################################################################

def generateDefFile(apis, args, additional_exports):

  code1 = []
  code2 = []
  code3 = []

  for i in apis:
    if i.name=='wgl' or i.name=='gl':
      for j in i.functions:
        code1.append('  %s'%j.name)
        code2.append('  r%s'%j.name)
    if i.name=='cgl' or i.name=='gl':
      for j in i.functions:
        code3.append('_%s'%j.name)
  code1.sort()
  code2.sort()
  code3.sort()

  code1.insert( 0, '  SetPixelFormat' )
  code2.insert( 0, '  SetPixelFormat' )

  # RegalMakeCurrent, RegalSetErrorCallback, etc

  code1 += ['  %s' % export for export in additional_exports]
  code2 += ['  %s' % export for export in additional_exports]
  code3 += ['_%s' % export for export in additional_exports]

  outputCode( '%s/Regal.def'  % args.srcdir, 'EXPORTS\n' + '\n'.join(code1))
  outputCode( '%s/Regalm.def' % args.srcdir, 'EXPORTS\n' + '\n'.join(code2))
  outputCode( '%s/export_list_mac.txt' % args.srcdir, '# File: export_list\n' + '\n'.join(code3))
