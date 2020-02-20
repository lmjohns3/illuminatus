import React, {Component} from "react"
import {Link, useParams} from "react-router-dom"
import ReactCrop from "react-image-crop"
import Select from "react-select"
import axios from "axios"

class Cluster extends Component {
    render() {
        return <div className="cluster">CLUSTER {useParams().query}</div>
    }
}

export default Cluster
