import axios from 'axios'
import {hsluvToHex} from 'hsluv'
import React from 'react'
import {useLocation} from 'react-router-dom'
import CreatableSelect from 'react-select/creatable'

import {ConfigContext} from './utils'

const ICONS = ['🗓', '⌚', '📷', '🌍', '🙋']

const CLASSES = {'🗓': 'date', '⌚': 'time', '📷': 'kit', '🌍': 'geo', '🙋': 'user'}

const PATTERNS = [
  // Year.
  {re: /^(19|20)\d\d$/, hue: 36, icon: 0},
  // Month.
  {re: /^january$/, hue: 72, icon: 0},
  {re: /^february$/, hue: 72, icon: 0},
  {re: /^march$/, hue: 72, icon: 0},
  {re: /^april$/, hue: 72, icon: 0},
  {re: /^may$/, hue: 72, icon: 0},
  {re: /^june$/, hue: 72, icon: 0},
  {re: /^july$/, hue: 72, icon: 0},
  {re: /^august$/, hue: 72, icon: 0},
  {re: /^september$/, hue: 72, icon: 0},
  {re: /^october$/, hue: 72, icon: 0},
  {re: /^november$/, hue: 72, icon: 0},
  {re: /^december$/, hue: 72, icon: 0},
  // Day of month.
  {re: /^\d(st|nd|rd|th)$/, hue: 108, icon: 0},
  {re: /^\d\d(st|nd|rd|th)$/, hue: 108, icon: 0},
  // Day of week.
  {re: /^sunday$/, hue: 144, icon: 0},
  {re: /^monday$/, hue: 144, icon: 0},
  {re: /^tuesday$/, hue: 144, icon: 0},
  {re: /^wednesday$/, hue: 144, icon: 0},
  {re: /^thursday$/, hue: 144, icon: 0},
  {re: /^friday$/, hue: 144, icon: 0},
  {re: /^saturday$/, hue: 144, icon: 0},
  // Time of day.
  {re: /^12am$/, hue: 180, icon: 1},
  {re: /^\dam$/, hue: 180, icon: 1},
  {re: /^\d\dam$/, hue: 180, icon: 1},
  {re: /^12pm$/, hue: 180, icon: 1},
  {re: /^\dpm$/, hue: 180, icon: 1},
  {re: /^\d\dpm$/, hue: 180, icon: 1},
  // Camera.
  {re: /^kit-\S+$/, hue: 216, icon: 2},
  // Aperture.
  {re: /^ƒ-\d$/, hue: 252, icon: 2},
  {re: /^ƒ-\d\d$/, hue: 252, icon: 2},
  {re: /^ƒ-\d\d\d$/, hue: 252, icon: 2},
  // Focal length.
  {re: /^\dmm$/, hue: 288, icon: 2},
  {re: /^\d\dmm$/, hue: 288, icon: 2},
  {re: /^\d\d\dmm$/, hue: 288, icon: 2},
  {re: /^\d\d\d\dmm$/, hue: 288, icon: 2},
  // Geolocation.
  {re: /^lat-\S+$/, hue: 324, icon: 3},
  {re: /^lng-\S+$/, hue: 324, icon: 3},
  {re: /^in-\S+$/, hue: 324, icon: 3},
  // User-defined.
  {re: /^.*$/, hue: 0, icon: 4},
]


const patternForTag = name => {
  const found = {label: name, value: name};
  PATTERNS.some((patt, p) => {
    if (patt.re.test(name)) {
      found.colors = {backgroundColor: hsluvToHex([patt.hue, 100, 80]),
                      color: hsluvToHex([patt.hue, 100, 20])};
      found.icon = patt.icon;
      found.order = p;
      return true;
    }
    return false;
  });
  return found;
}


const countAssetTags = assets => {
  const tags = {}, groups = ICONS.map(() => []);
  assets.forEach(asset => {
    asset.tags.forEach(name => {
      if (!tags[name]) {
        const tag = {name, label: name, value: name, count: 0, ...patternForTag(name)};
        groups[tag.icon].push(tag);
        tags[name] = tag;
      }
      tags[name].count++;
    });
  });
  // Sort tags within each group by the index of their pattern, then by name.
  const cmp = (s, t) => s.order < t.order ? -1 : s.order > t.order ? 1 :
                        s.name < t.name ? -1 : s.name > t.name ? 1 : 0;
  return groups.map((group, i) => ({icon: ICONS[i], tags: group.sort(cmp), index: i}));
}


const Tags = ({icon, tags, clickHandler, className}) => (
  <div key={icon} className={`tags ${className || ''} ${CLASSES[icon]}`}>
    <span className='icon'>{icon}</span>
    <ul>{tags.map(tag => (
      <li key={tag.name}
          className={`tag ${useLocation().pathname.indexOf('/'+tag.name+'/') >= 0 ? 'active' : ''}`}
          style={{...tag.colors, cursor: clickHandler ? 'pointer' : 'default'}}>
        <span onClick={clickHandler ? clickHandler(tag) : null}>{tag.name}</span>
      </li>
    ))}</ul>
  </div>)


const TagSelect = ({assets, activeAssets, className}) => {
  const changeTags = active => (options, about) => {
    if (about.action === 'create-option' || about.action === 'select-option') {
      active.forEach(({slug}) => axios.post(
        `/rest/asset/${slug}/${options[options.length - 1].value}/`));
    } else if (about.action === 'pop-value' || about.action === 'remove-value') {
      active.forEach(({slug}) => axios.delete(
        `/rest/asset/${slug}/${about.removedValue.value}/`));
    }
  };

  return <ConfigContext.Consumer>{({tags}) => <CreatableSelect
      className={`${className || ''} tag-select`}
      key={assets.length}
      isClearable={false}
      isMulti={true}
      defaultValue={
        assets.length === 0 ? [] : [...new Set(
          assets.reduce((acc, a) => [...acc, ...a.tags], [])
        )].map(patternForTag).filter(({icon}) => icon > 2)
      }
      options={tags.map(({name}) => patternForTag(name)).filter(({icon}) => icon > 2)}
      onChange={changeTags(activeAssets && activeAssets.length ? activeAssets : assets)}
      placeholder='Add tag...'
      styles={{
        control: base => ({...base, background: '#666', borderColor: '#666'}),
        placeholder: base => ({...base, color: '#111'}),
        option: (base, {data}) => ({
          ...base,
          ...data.colors,
          display: 'inline-block',
          float: 'left',
          width: 'auto',
          margin: '0.2em',
          padding: '0.2em 0.4em',
          borderRadius: '3px',
          cursor: 'pointer',
        }),
        menu: base => ({...base, background: '#666'}),
        multiValue: (base, {data}) => ({...base, ...data.colors}),
        multiValueLabel: base => ({...base, fontSize: '100%'}),
        multiValueRemove: base => ({...base, fontSize: '100%'}),
  }} />}</ConfigContext.Consumer>;
}

export {countAssetTags, patternForTag, Tags, TagSelect}
