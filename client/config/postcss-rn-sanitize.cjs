/**
 * Taro RN：在 css-to-react-native 之前粗化样式；Token 对齐 `design-tokens-rn.cjs`。
 * padding/margin **简写**在 pxtransform→scalePx2dp 后与简写解析组合易炸，统一拆成四条长写。
 */

const postcss = require('postcss')
const { TOKENS } = require('./design-tokens-rn.cjs')

function substituteVars(val) {
  /** 支持 var(--tok) 与 var(--tok, #hex|rgba(..)) ，否则残留 function 令牌会干掉 background 简写解析 */
  return String(val || '').replace(
    /\bvar\s*\(\s*(--[\w-]+)\s*(?:,\s*(#[0-9a-fA-F]{3,8}|rgba?\s*\([^)]+\))\s*)?\)/gi,
    (_, name, fb) => {
      if (TOKENS[name] !== undefined) return TOKENS[name]
      if (fb) return String(fb).trim()
      return TOKENS['--color-bg-page'] || '#f4f6fc'
    },
  )
}

function flattenGradientValue(val) {
  const s = String(val || '')
    .replace(/\s+/g, ' ')
    .trim()

  const vars = s.match(/var\s*\([^)]+\)/g)
  if (vars && vars.length) {
    const nm = /--([\w-]+)/.exec(vars[0])
    if (nm && TOKENS[`--${nm[1]}`]) return TOKENS[`--${nm[1]}`]
  }

  const hex = s.match(/#[0-9a-fA-F]{3,8}\b/)
  if (hex) return hex[0]

  const rgb = s.match(/rgba?\s*\([^)]+\)/)
  if (rgb) return rgb[0]

  return 'transparent'


}

function stripCssFunctions(val) {
  let v = String(val || '')
  v = v.replace(/env\s*\(\s*[^)]+\)/gi, '0')
  v = v.replace(/calc\s*\(\s*([^)]+)\)/gi, (_, inner) => {
    const inn = String(inner)
    const rpx = inn.match(/(\d+(?:\.\d+)?)\s*rpx/i)
    if (rpx) return `${rpx[1]}rpx`
    const px = inn.match(/(\d+(?:\.\d+)?)\s*px/i)
    if (px) return `${px[1]}px`
    return '0'
  })
  v = v.replace(/\b(min|max|clamp)\s*\(\s*([^)]+)\)/gi, (_, __, inner) => {
    const inn = String(inner)
    const rpx = inn.match(/(\d+(?:\.\d+)?)\s*rpx/i)
    if (rpx) return `${rpx[1]}rpx`
    const px = inn.match(/(\d+(?:\.\d+)?)\s*px/i)
    if (px) return `${px[1]}px`
    return '0'
  })
  return v


}

/** inherit / unset / initial：按属性粗化，避免 tokenizer 失败 */
function sanitizeKeywords(val, prop) {
  let v = String(val || '')
  if (!/\b(inherit|unset|initial)\b/i.test(v)) return v


  if (/radius/i.test(prop))
    return v.replace(/\binherit\b/gi, '20rpx').replace(/\b(unset|initial)\b/gi, '0')


  return v.replace(/\b(inherit|unset|initial)\b/gi, '0')


}


function toFourSides(expandedVal) {
  const parts = String(expandedVal)
    .trim()
    .split(/\s+/)


    .filter(Boolean)


  if (parts.length === 0) return ['0', '0', '0', '0']


  let t


  let r


  let b


  let l


  if (parts.length === 1) {


    t = r = b = l = parts[0]


  } else if (parts.length === 2) {


    t = b = parts[0]


    r = l = parts[1]


  } else if (parts.length === 3) {


    t = parts[0]


    r = l = parts[1]


    b = parts[2]


  } else {


    t = parts[0]


    r = parts[1]


    b = parts[2]


    l = parts[3]


  }


  return [t, r, b, l]


}


/** taro-css-to-react-native LENGTH 不认 rpx；简写 tokenizer 会先炸 */


function normalizeRpxToPxCssValue(s) {


  return String(s).replace(/\b(\d+(?:\.\d+)?)rpx\b/gi, '$1px')


}


/** border / border-*-* 简写在 scalePx2dp + tokenizer 组合下易报错，拆成 *-width / *-style / *-color */


function splitBorderShorthand(decl, postcss, vResolved, side) {


  const pfx = side ? `border-${side}` : 'border'


  const t = String(vResolved).trim()


  if (/^none$/i.test(t)) {


    decl.replaceWith([
      postcss.decl({ prop: `${pfx}-width`, value: '0' }),
      postcss.decl({ prop: `${pfx}-color`, value: 'transparent' }),
    ])
    return
  }


  const m = t.match(/^(\S+)\s+(solid|dashed|dotted)\s+(.+)$/i)


  if (m) {


    /* RN View 不认 borderTopStyle 等分边样式，仅宽度+颜色；默认为 solid */


    decl.replaceWith([
      postcss.decl({ prop: `${pfx}-width`, value: normalizeRpxToPxCssValue(m[1]) }),
      postcss.decl({ prop: `${pfx}-color`, value: m[3].trim() }),
    ])
    return
  }


  decl.remove()


}

function postcssRnSanitize() {
  return {


    postcssPlugin: 'postcss-rn-sanitize',


    Rule(rule) {


      const s = rule.selector || ''
      if (
        /::?(before|after|placeholder)|\[[^\]]+\]|:(active|focus|hover|visited|disabled)\b/i.test(
          s,
        )
      ) {
        rule.remove()
      }


    },


    Declaration(decl) {


      decl.important = false


      const prop = String(decl.prop || '')


      if (/^transition|^animation/i.test(prop) || prop.startsWith('-webkit-')) {


        decl.remove()


        return


      }


      if (prop.startsWith('--')) {


        decl.remove()


        return


      }


      if (prop === 'gap') {


        decl.remove()


        return


      }


      if (prop === 'flex' && typeof decl.value === 'string' && /%/.test(decl.value)) {
        decl.value = '1'
      }


      if (prop === 'inset') {
        const raw = String(decl.value).replace(/\s/g, '')
        if (/^0(p[xt])?$/.test(raw) || raw === '0') {


          decl.replaceWith([
            postcss.decl({ prop: 'top', value: '0' }),
            postcss.decl({ prop: 'left', value: '0' }),
            postcss.decl({ prop: 'right', value: '0' }),
            postcss.decl({ prop: 'bottom', value: '0' }),
          ])


        } else {


          decl.remove()


        }


        return


      }


      let v = decl.value


      if (!v || typeof v !== 'string') return


      v = substituteVars(v)


      if (/\b(linear|radial)-gradient\s*\(/i.test(v)) v = flattenGradientValue(v)


      if (/\b(calc|env|min|max|clamp)\s*\(/i.test(v)) v = stripCssFunctions(v)


      if (/\b(inherit|unset|initial)\b/i.test(v)) v = sanitizeKeywords(v, prop)


      if (prop === 'letter-spacing' && /^-/.test(String(v).trim())) {


        decl.remove()


        return


      }


      if (/^padding$/i.test(prop)) {


        const [t, ri, bt, lf] = toFourSides(v)


        decl.replaceWith([
          postcss.decl({ prop: 'padding-top', value: t }),


          postcss.decl({ prop: 'padding-right', value: ri }),


          postcss.decl({ prop: 'padding-bottom', value: bt }),


          postcss.decl({ prop: 'padding-left', value: lf }),


        ])


        return


      }


      if (/^margin$/i.test(prop)) {


        const [t, ri, bt, lf] = toFourSides(v)


        decl.replaceWith([
          postcss.decl({ prop: 'margin-top', value: t }),


          postcss.decl({ prop: 'margin-right', value: ri }),


          postcss.decl({ prop: 'margin-bottom', value: bt }),


          postcss.decl({ prop: 'margin-left', value: lf }),


        ])


        return


      }


      if (/^border$/i.test(prop)) {


        splitBorderShorthand(decl, postcss, v, null)


        return


      }


      const bd = /^border-(top|right|bottom|left)$/i.exec(prop)


      if (bd) {


        splitBorderShorthand(decl, postcss, v, bd[1].toLowerCase())


        return


      }


      /* border-radius 简写必须由 LENGTH(px) tokenizer 吃掉；rpx 会变成裸 word 报错 */



      if (/^border-radius$/i.test(prop)) {


        decl.value = normalizeRpxToPxCssValue(v)


        return


      }


      if (/^border-width$/i.test(prop) || /^border-(top|right|bottom|left)-width$/i.test(prop)) {


        decl.value = normalizeRpxToPxCssValue(v)


        return


      }


      if (/^box-shadow$/i.test(prop) || /^text-shadow$/i.test(prop)) {


        decl.value = normalizeRpxToPxCssValue(v)


        return


      }


      /* translate(-50%,-50%)：transform 只解析 LENGTH(px)，百分比会报错 */


      if (/^transform$/i.test(prop)) {


        if (/%/.test(v)) {


          decl.remove()


          return


        }


        decl.value = normalizeRpxToPxCssValue(v)


        return


      }


      /** flex 简写的 flex-basis（如 36rpx）只认 LENGTH(px) */


      if (/^flex$/i.test(prop)) {


        decl.value = normalizeRpxToPxCssValue(v)


        return


      }


      decl.value = v


    },


  }


}

postcssRnSanitize.postcss = true
module.exports = postcssRnSanitize
