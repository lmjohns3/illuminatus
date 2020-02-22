import React, {Component} from "react"
import {Link, useParams} from "react-router-dom"
import axios from "axios"

const Cluster = () => (
  <div className="cluster">CLUSTER {useParams().query}</div>
)

export default Cluster
