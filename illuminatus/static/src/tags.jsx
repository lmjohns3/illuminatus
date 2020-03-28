import React, {Fragment, useState} from "react"
import {Link, useLocation} from "react-router-dom"
import {hsluvToHex} from "hsluv"

const TAG_PATTERNS = [
  // Year.
  {re: /^(19|20)\d\d$/, hue: 90, block: 0},
  // Month.
  {re: /^january$/, hue: 120, block: 0},
  {re: /^february$/, hue: 120, block: 0},
  {re: /^march$/, hue: 120, block: 0},
  {re: /^april$/, hue: 120, block: 0},
  {re: /^may$/, hue: 120, block: 0},
  {re: /^june$/, hue: 120, block: 0},
  {re: /^july$/, hue: 120, block: 0},
  {re: /^august$/, hue: 120, block: 0},
  {re: /^september$/, hue: 120, block: 0},
  {re: /^october$/, hue: 120, block: 0},
  {re: /^november$/, hue: 120, block: 0},
  {re: /^december$/, hue: 120, block: 0},
  // Day of month.
  {re: /^\d(st|nd|rd|th)$/, hue: 150, block: 0},
  {re: /^\d\d(st|nd|rd|th)$/, hue: 150, block: 0},
  // Day of week.
  {re: /^sunday$/, hue: 180, block: 0},
  {re: /^monday$/, hue: 180, block: 0},
  {re: /^tuesday$/, hue: 180, block: 0},
  {re: /^wednesday$/, hue: 180, block: 0},
  {re: /^thursday$/, hue: 180, block: 0},
  {re: /^friday$/, hue: 180, block: 0},
  {re: /^saturday$/, hue: 180, block: 0},
  // Time of day.
  {re: /^12am$/, hue: 210, block: 1},
  {re: /^\dam$/, hue: 210, block: 1},
  {re: /^\d\dam$/, hue: 210, block: 1},
  {re: /^12pm$/, hue: 210, block: 1},
  {re: /^\dpm$/, hue: 210, block: 1},
  {re: /^\d\dpm$/, hue: 210, block: 1},
  // Camera.
  {re: /^kit:\S+$/, hue: 240, block: 2},
  // Aperture.
  {re: /^ƒ-\d$/, hue: 240, block: 2},
  {re: /^ƒ-\d\d$/, hue: 240, block: 2},
  {re: /^ƒ-\d\d\d$/, hue: 240, block: 2},
  // Focal length.
  {re: /^\dmm$/, hue: 240, block: 2},
  {re: /^\d\dmm$/, hue: 240, block: 2},
  {re: /^\d\d\dmm$/, hue: 240, block: 2},
  {re: /^\d\d\d\dmm$/, hue: 240, block: 2},
  // Geolocation.
  {re: /^country:\S+$/, hue: 270, block: 3},
  {re: /^state:\S+$/, hue: 270, block: 3},
  {re: /^city:\S+$/, hue: 270, block: 3},
  {re: /^place:\S+$/, hue: 270, block: 3},
  // User-defined.
  {re: /^.*$/, hue: 0, block: 4},
]

export default function Tags({assets, startVisible, href}) {
  if (assets.length === 0)
    return null;

  const pathname = useLocation().pathname, tags = {}, blocks = [
    {icon: "🗓", active: [], other: []},
    {icon: "⌚", active: [], other: []},
    {icon: "📷", active: [], other: []},
    {icon: "🌍", active: [], other: []},
    {icon: "🙋", active: [], other: []},
  ];

  // Count up the tags in our assets.
  assets.forEach(asset => {
    asset.tags.forEach(t => {
      if (!tags[t]) {
        const tag = {name: t, count: 0, active: pathname.indexOf(`/${t}/`) >= 0};
        TAG_PATTERNS.some((pattern, p) => {
          if (pattern.re.test(t)) {
            blocks[pattern.block][tag.active ? "active" : "other"].push(t);
            tag.hue = pattern.hue;
            tag.order = p;
            return true;
          }
          return false;
        });
        tags[t] = tag;
      }
      tags[t].count++;
    });
  });

  return <div className="tags">{
    blocks.map(block => <Block key={block.icon}
                               block={block}
                               tags={tags}
                               startVisible={startVisible}
                               assetCount={assets.length}
                               href={href} />)
  }</div>;
}


const Block = ({block, tags, startVisible, assetCount, href}) => {
  if ((block.active.length <= 0) && (block.other.length <= 0))
    return null;

  const [visible, setVisible] = useState(startVisible);

  // Sort tags within each block by the index of their pattern, then by name.
  const cmp = (m, n) => {
    const s = tags[m], t = tags[n];
    return s.order < t.order ? -1 : s.order > t.order ? 1 :
           s.name < t.name ? -1 : s.name > t.name ? 1 : 0;
  };
  block.active.sort(cmp);
  block.other.sort(cmp);

  const render = names => names.map(
    name => <Tag key={name} tag={tags[name]} assetCount={assetCount} href={href} />
  );

  return <Fragment>
    {render(block.active)}
    <span className="icon" onClick={() => setVisible(!visible)}>{block.icon}</span>
    {visible ? render(block.other) : null}
  </Fragment>;
}


const Tag = ({tag, assetCount, href}) => {
  const path = useLocation().pathname
      , span = <span className="tag" style={{
    backgroundColor: hsluvToHex([tag.hue, 100, 90]),
    opacity: Math.log(3 + tag.count) / Math.log(1 + assetCount),
  }}>{tag.name}</span>;
  return href ? <Link to={href(tag.name, path)}>{span}</Link> : span;
}
