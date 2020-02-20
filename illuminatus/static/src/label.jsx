import React, {Component} from "react"
import {Link, useParams} from "react-router-dom"
import ReactCrop from "react-image-crop"
import Select from "react-select"
import axios from "axios"

class Label extends Component {
    render() {
        return <div className="label">LABEL {useParams().id}</div>
    }
}

export default Label
