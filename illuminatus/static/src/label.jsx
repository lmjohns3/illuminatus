import React, {Component} from "react"
import {Link, useParams} from "react-router-dom"
import Select from "react-select"
import axios from "axios"

const Label = () => (
    <div className="label">LABEL {useParams().id}</div>
)

export default Label

/*
const TagSelections = (props) => (
    <Select
    clearButton
    defaultSelected={options.slice(0, 5)}
    labelKey="name"
    multiple
    options={options}
    placeholder="Tags..." />)

*/
